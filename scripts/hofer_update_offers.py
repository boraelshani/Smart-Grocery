#!/usr/bin/env python3
"""
Hofer promotion scraper
========================
Scrapes the Hofer Angebote (weekly deals) pages with Playwright to get
was-prices, badge labels, and offer types, then stores them in the DB.

Strategy:
  1. Load deal product URLs from today's + upcoming Angebote pages
  2. For each deal URL, render with Playwright to get was-price + badges
  3. Detect offer type from badge text (BOGO, multibuy, percentage, fixed)
  4. Update product_store.is_preis_gesenkt and upsert offers/promotions/targets
  5. Deactivate old Hofer promotions no longer in the deals list

Run:
    python3 scripts/hofer_update_offers.py
    python3 scripts/hofer_update_offers.py --dry-run
"""

import argparse
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import execute_values
from playwright.sync_api import sync_playwright, Page

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / '.env')

STORE_ID  = 'hofer'
BASE_URL  = 'https://www.hofer.at'
UA        = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
             'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')

# Angebote pages to scrape (today + next few days to catch upcoming deals)
def _angebote_urls() -> List[str]:
    today = date.today()
    urls = []
    # schnell-zugreifen = "on sale right now"
    urls.append(f'{BASE_URL}/de/angebote/schnell-zugreifen.html')
    # Date-specific pages for today and ±3 days
    from datetime import timedelta
    for delta in range(-1, 5):
        d = today + timedelta(days=delta)
        urls.append(f'{BASE_URL}/de/angebote/date.{d.strftime("%d-%m-%Y")}.html')
    return urls


# ── Offer detection ────────────────────────────────────────────────────────────
_OFFER_RE = [
    # N+M gratis
    (re.compile(r'(\d+)\s*\+\s*(\d+)\s*(gratis|free|geschenkt)', re.IGNORECASE), 'bogo'),
    # N für M  (3 für 2)
    (re.compile(r'(\d+)\s*f[uü]r\s*(\d+)', re.IGNORECASE), 'bogo_fuer'),
    # buy N save X%
    (re.compile(r'(?:ab\s*|kaufen?\s*)(\d+).*?(\d+(?:\.\d+)?)\s*%', re.IGNORECASE), 'multibuy'),
    # X% ab N Stück
    (re.compile(r'(\d+(?:\.\d+)?)\s*%.*?ab\s*(\d+)', re.IGNORECASE), 'multibuy_pct_first'),
    # -X% / X% Rabatt
    (re.compile(r'(?:-\s*)?(\d+(?:\.\d+)?)\s*%\s*(?:rabatt|erm.ssigung|g.nstiger|billiger|off)?', re.IGNORECASE), 'percentage'),
    # fixed saving €X
    (re.compile(r'(?:spare|g.nstiger|billiger)\s*€?\s*(\d+(?:[.,]\d+)?)', re.IGNORECASE), 'fixed'),
    # generic
    (re.compile(r'\b(?:aktion|angebot|aktionspreis|sonderangebot)\b', re.IGNORECASE), 'aktion'),
]


def _parse_price(text: str) -> Optional[float]:
    if not text:
        return None
    clean = re.sub(r'[^\d,.]', '', text.strip()).replace(',', '.')
    try:
        return float(clean) if clean else None
    except ValueError:
        return None


def _detect_offer(badge_texts: List[str], was_price: Optional[float],
                  current_price: Optional[float]) -> Dict:
    combined = ' '.join(badge_texts)

    for pattern, dtype in _OFFER_RE:
        m = pattern.search(combined)
        if not m:
            continue

        if dtype == 'bogo':
            try:
                return {'discount_type': 'bogo',
                        'discount_value': int(m.group(2)),
                        'min_quantity': int(m.group(1)),
                        'label': m.group(0).strip()}
            except (IndexError, ValueError):
                pass

        elif dtype == 'bogo_fuer':
            try:
                get_qty, pay_qty = int(m.group(1)), int(m.group(2))
                if get_qty > pay_qty:
                    return {'discount_type': 'bogo',
                            'discount_value': get_qty - pay_qty,
                            'min_quantity': pay_qty,
                            'label': m.group(0).strip()}
            except (IndexError, ValueError):
                pass

        elif dtype == 'multibuy':
            try:
                return {'discount_type': 'multibuy',
                        'discount_value': float(m.group(2).replace(',', '.')),
                        'min_quantity': int(m.group(1)),
                        'label': m.group(0).strip()}
            except (IndexError, ValueError):
                pass

        elif dtype == 'multibuy_pct_first':
            try:
                return {'discount_type': 'multibuy',
                        'discount_value': float(m.group(1).replace(',', '.')),
                        'min_quantity': int(m.group(2)),
                        'label': m.group(0).strip()}
            except (IndexError, ValueError):
                pass

        elif dtype == 'percentage':
            try:
                pct = float(m.group(1).replace(',', '.'))
                if 0 < pct <= 90:
                    return {'discount_type': 'percentage', 'discount_value': pct,
                            'min_quantity': 1, 'label': m.group(0).strip()}
            except (IndexError, ValueError):
                pass

        elif dtype == 'fixed':
            try:
                return {'discount_type': 'fixed',
                        'discount_value': float(m.group(1).replace(',', '.')),
                        'min_quantity': 1, 'label': m.group(0).strip()}
            except (IndexError, ValueError):
                pass

        elif dtype == 'aktion':
            # Fallthrough — compute % from prices if available
            pass

    # No badge match — compute % from was_price if available
    if was_price and current_price and was_price > current_price:
        pct = round((was_price - current_price) / was_price * 100, 1)
        return {'discount_type': 'percentage', 'discount_value': pct,
                'min_quantity': 1, 'label': f'Statt €{was_price:.2f}'}

    return {}


# ── Playwright scraping ────────────────────────────────────────────────────────
def _get_deal_urls(page: Page, angebote_urls: List[str]) -> List[str]:
    """Collect all product URLs from Angebote pages."""
    seen = set()
    result = []
    for url in angebote_urls:
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=40000)
            page.wait_for_timeout(2500)
            html = page.content()
            links = re.findall(r'href="(/de/p\.[^"]+\.html)"', html)
            for link in links:
                full = BASE_URL + link
                if full not in seen:
                    seen.add(full)
                    result.append(full)
            print(f'  {url.split("/")[-1]}: {len(links)} products')
        except Exception as e:
            print(f'  [!] Failed {url}: {e}')
    return result


def _scrape_deal_product(page: Page, url: str) -> Optional[Dict]:
    """Scrape a single deal product page. Returns offer data or None."""
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(1500)
        html = page.content()

        # Product code from URL
        code_m = re.search(r'\.(\d{9,}(?:-\d+)?)\.html', url)
        product_code = code_m.group(1) if code_m else None

        # Current price
        price_m = re.search(r'data-price="([^"]+)"', html)
        current_price = _parse_price(price_m.group(1)) if price_m else None

        # Was-price — Hofer renders this as a crossed-out span after JS runs
        was_price = None
        # Pattern 1: pdp_price__was class
        was_m = re.search(r'class="[^"]*pdp_price__was[^"]*"[^>]*>\s*(?:Statt\s*)?€?\s*([\d,\.]+)', html, re.IGNORECASE)
        if was_m and '{{' not in was_m.group(0):
            was_price = _parse_price(was_m.group(1))
        # Pattern 2: <s> tag with price not in cart template
        if not was_price:
            for s_m in re.finditer(r'<s[^>]*>\s*€?\s*([\d,\.]+)\s*</s>', html):
                ctx_before = html[max(0, s_m.start()-300):s_m.start()]
                if '{{' not in ctx_before and 'cartEntry' not in ctx_before:
                    v = _parse_price(s_m.group(1))
                    if v and current_price and v > current_price:
                        was_price = v
                        break
        # Pattern 3: rendered Statt text not in template
        if not was_price:
            for statt_m in re.finditer(r'Statt\s*<[^>]+>\s*€?\s*([\d,\.]+)', html, re.IGNORECASE):
                ctx = html[max(0, statt_m.start()-100):statt_m.start()]
                if '{{' not in ctx and 'cartEntry' not in ctx:
                    v = _parse_price(statt_m.group(1))
                    if v and current_price and v > current_price:
                        was_price = v
                        break

        # Badge/label texts (offer labels rendered after JS)
        badge_section = re.search(r'badges_items_list[^>]*>(.*?)</ul>', html, re.DOTALL)
        badge_texts = []
        if badge_section:
            raw_alts = re.findall(r'alt="([^"]+)"', badge_section.group(1))
            badge_texts = [a for a in raw_alts if any(
                kw in a.lower() for kw in ['aktion', 'gratis', 'rabatt', '%', 'für', 'bonus', 'angebot', 'promo', 'neu']
            )]
            # Also grab visible text in badges
            badge_labels = re.findall(r'class="[^"]*badge[^"]*"[^>]*>([^<{]{3,})<', badge_section.group(1))
            badge_texts += [b.strip() for b in badge_labels if b.strip() and '{{' not in b]

        offer = _detect_offer(badge_texts, was_price, current_price)

        if not offer and not was_price:
            return None  # not actually on promotion

        return {
            'product_code': product_code,
            'url': url,
            'current_price': current_price,
            'was_price': was_price,
            'badge_texts': badge_texts,
            'offer': offer,
        }
    except Exception as e:
        print(f'    [!] Error scraping {url}: {e}')
        return None


# ── DB helpers ─────────────────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_product_ids_by_code(cursor, codes: List[str]) -> Dict[str, int]:
    """Return product_code → product_id mapping using fingerprint."""
    if not codes:
        return {}
    fps = [f'hofer_{c}' for c in codes]
    cursor.execute("SELECT id, fingerprint FROM products WHERE fingerprint = ANY(%s)", (fps,))
    return {fp.replace('hofer_', ''): pid for pid, fp in cursor.fetchall()}


def _setup_promotion(cursor) -> int:
    today     = date.today()
    promo_name = f'Hofer Aktionen {today.isoformat()}'
    cursor.execute(
        "UPDATE promotions SET is_active = FALSE WHERE name LIKE %s AND name != %s AND is_active = TRUE",
        ('Hofer Aktionen %', promo_name)
    )
    cursor.execute("""
        INSERT INTO promotions (name, description, start_date, is_active, created_at)
        VALUES (%s, %s, %s, TRUE, %s)
        ON CONFLICT DO NOTHING RETURNING id
    """, (promo_name, f'Hofer Angebote {today.isoformat()}', today, _now()))
    row = cursor.fetchone()
    if not row:
        cursor.execute("SELECT id FROM promotions WHERE name = %s LIMIT 1", (promo_name,))
        row = cursor.fetchone()
    return row[0]


def _save_deal(cursor, deal: Dict, code_to_pid: Dict[str, int],
               promo_id: int, dry_run: bool) -> bool:
    product_code = deal['product_code']
    pid = code_to_pid.get(product_code)
    if not pid:
        return False

    offer = deal['offer']
    current_price = deal['current_price']
    was_price = deal['was_price']

    if dry_run:
        print(f'  DRY: {product_code} price={current_price} was={was_price} '
              f'offer={offer.get("discount_type","?")} {offer.get("discount_value","")} '
              f'badges={deal["badge_texts"]}')
        return True

    # Mark product as on sale
    cursor.execute(
        "UPDATE product_store SET is_preis_gesenkt = TRUE, base_price = %s WHERE product_id = %s AND store_id = %s",
        (current_price, pid, STORE_ID)
    )

    if not offer:
        return True

    dtype  = offer['discount_type']
    dval   = offer['discount_value']
    min_q  = offer.get('min_quantity', 1)
    label  = offer.get('label', '')

    if dtype == 'bogo':
        name = f"Hofer {min_q}+{dval} Gratis"
    elif dtype == 'multibuy':
        name = f"Hofer {dval}% ab {min_q} Stück"
    elif dtype == 'percentage':
        name = f"Hofer -{round(dval)}% Rabatt"
    elif dtype == 'fixed':
        name = f"Hofer €{dval:.2f} günstiger"
    else:
        name = "Hofer Aktion"

    # Upsert offer
    cursor.execute("""
        INSERT INTO offers (name, description, discount_type, discount_value,
                            min_quantity, is_active, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, TRUE, %s, %s)
        ON CONFLICT DO NOTHING RETURNING id
    """, (name, label, dtype, dval, min_q, _now(), _now()))
    row = cursor.fetchone()
    if not row:
        cursor.execute("SELECT id FROM offers WHERE name = %s LIMIT 1", (name,))
        row = cursor.fetchone()
    if not row:
        return False
    offer_id = row[0]

    # Link promo → offer
    cursor.execute(
        "UPDATE promotions SET offer_id = %s WHERE id = %s AND offer_id IS NULL",
        (offer_id, promo_id)
    )

    # Upsert promotion target
    cursor.execute("""
        INSERT INTO promotion_targets (promotion_id, product_id, store_id, created_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (promotion_id, product_id, store_id) DO NOTHING
    """, (promo_id, pid, STORE_ID, _now()))

    return True


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Print without writing to DB')
    args = parser.parse_args()

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print('[!] DATABASE_URL not set'); sys.exit(1)

    conn   = psycopg2.connect(db_url)
    cursor = conn.cursor()

    angebote_urls = _angebote_urls()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-dev-shm-usage',
        ])
        ctx = browser.new_context(
            user_agent=UA,
            locale='de-AT',
            viewport={'width': 1280, 'height': 800},
        )
        page = ctx.new_page()

        print('[HOFER OFFERS] Collecting deal URLs...')
        deal_urls = _get_deal_urls(page, angebote_urls)
        print(f'[HOFER OFFERS] Found {len(deal_urls)} unique deal products')

        if not deal_urls:
            print('[HOFER OFFERS] No deals found — exiting')
            browser.close()
            return

        print('[HOFER OFFERS] Scraping deal pages...')
        deals = []
        for i, url in enumerate(deal_urls, 1):
            result = _scrape_deal_product(page, url)
            if result:
                deals.append(result)
                offer_info = result['offer']
                print(f'  [{i}/{len(deal_urls)}] ✓ {url.split("/")[-1][:50]} '
                      f'| price={result["current_price"]} was={result["was_price"]} '
                      f'| {offer_info.get("discount_type","?")} {offer_info.get("discount_value","")} '
                      f'| badges={result["badge_texts"]}')
            else:
                print(f'  [{i}/{len(deal_urls)}] - {url.split("/")[-1][:50]} (no promo detected)')
            time.sleep(0.5)

        browser.close()

    print(f'\n[HOFER OFFERS] Detected {len(deals)} products with promotions')

    if not deals:
        cursor.close(); conn.close()
        return

    # Reconnect — the Playwright scrape may have timed out the DB connection
    try:
        cursor.execute("SELECT 1")
    except Exception:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

    # Match to DB products
    codes = [d['product_code'] for d in deals if d['product_code']]
    code_to_pid = _get_product_ids_by_code(cursor, codes)
    print(f'[HOFER OFFERS] Matched {len(code_to_pid)}/{len(codes)} products in DB')

    if not args.dry_run:
        promo_id = _setup_promotion(cursor)
        conn.commit()
    else:
        promo_id = -1

    saved = 0
    for deal in deals:
        if _save_deal(cursor, deal, code_to_pid, promo_id, args.dry_run):
            saved += 1

    if not args.dry_run:
        conn.commit()

    print(f'\n[HOFER OFFERS] DONE — {saved} deals saved'
          + (' (DRY RUN)' if args.dry_run else ''))
    cursor.close()
    conn.close()


if __name__ == '__main__':
    main()
