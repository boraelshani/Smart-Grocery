#!/usr/bin/env python3
"""
Scrape the BILLA search catalog and replace the current PostgreSQL product data.

The script:
- clears existing products, offers, and price history in PostgreSQL
- crawls every BILLA search page from https://www.billa.at/suche/%20
- extracts product data from the Nuxt SSR payload embedded in the HTML
- stores products in `products` and prices in `offers`
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import execute_values
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from scrapers.real_billa_scraper import RealBillaScraper
# Use existing categoriser to map product names to our category taxonomy
from scripts.pipeline.categoriser import classify_product


SEARCH_URL = "https://www.billa.at/suche/%20"
STORE_ID = "billa"
STORE_NAME = "BILLA"
STORE_WEBSITE = "https://www.billa.at"
STORE_LOGO = "https://shop.billa.at/img/logo.png"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_database_uri() -> str:
    load_dotenv()
    database_uri = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI")
    if not database_uri:
        raise RuntimeError("DATABASE_URL or SQLALCHEMY_DATABASE_URI is not set.")
    return database_uri


def _get_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        }
    )
    return session


def _fetch_html(session: requests.Session, url: str, retries: int = 3, timeout: int = 30) -> str:
    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            return response.text
        except Exception as exc:  # pragma: no cover - network failures are environment dependent
            last_error = exc
            wait_seconds = min(8, attempt * 2)
            print(f"[BILLA] fetch failed on attempt {attempt}: {exc}")
            if attempt < retries:
                time.sleep(wait_seconds)
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def _get_total_pages(html: str) -> int:
    page_numbers = [int(match) for match in re.findall(r'href="/suche/%20\?page=(\d+)"', html)]
    if page_numbers:
        return max(page_numbers)
    return 1


def _get_nuxt_payload(html: str) -> Optional[list]:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NUXT_DATA__")
    if not script or not script.string:
        return None
    try:
        payload = json.loads(script.string)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, list) else None


def _as_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_price(raw_price: Any) -> Optional[float]:
    price = _as_float(raw_price)
    if price is None or price <= 0:
        return None
    if float(price).is_integer():
        price = price / 100.0
    return round(price, 2)


def _extract_price(product: Dict[str, Any]) -> Optional[float]:
    price_obj = product.get("price")
    candidates: List[Any] = []

    if isinstance(price_obj, dict):
        regular = price_obj.get("regular")
        if isinstance(regular, dict):
            candidates.extend(
                [
                    regular.get("value"),
                    regular.get("price"),
                    regular.get("amount"),
                    regular.get("promotionValue"),
                ]
            )
        else:
            candidates.append(regular)

        candidates.extend(
            [
                price_obj.get("value"),
                price_obj.get("price"),
                price_obj.get("currentPrice"),
                price_obj.get("basePrice"),
                price_obj.get("salePrice"),
                price_obj.get("promotionValue"),
            ]
        )
    else:
        candidates.append(price_obj)

    for candidate in candidates:
        normalized = _normalize_price(candidate)
        if normalized is not None:
            return normalized
    return None


def _extract_image(product: Dict[str, Any]) -> Optional[str]:
    images = product.get("images")
    if not isinstance(images, list):
        return None
    for image in images:
        if isinstance(image, str) and image.startswith("http"):
            return image
        if isinstance(image, dict):
            for key in ("url", "src", "image", "imageUrl"):
                candidate = image.get(key)
                if isinstance(candidate, str) and candidate.startswith("http"):
                    return candidate
    return None


def _extract_unit(product: Dict[str, Any], scraper: RealBillaScraper) -> Optional[str]:
    amount = product.get("amount")
    volume_short = product.get("volumeLabelShort")
    volume_long = product.get("volumeLabelLong")
    description = product.get("descriptionShort") or product.get("descriptionLong") or ""
    name = product.get("name") or ""

    # Return ONLY the unit, not the quantity + unit
    # volumeLabelShort is already just the unit (e.g., "l", "ml", "g", "kg", "stk", "st.", "pack")
    if volume_short and isinstance(volume_short, str):
        unit = volume_short.strip()
        # Normalize common abbreviations
        unit = {"st.": "stk", "pcs": "stk", "pack": "pack"}.get(unit, unit)
        return unit if unit else None

    text_candidates = [name, description, volume_long or ""]
    for text in text_candidates:
        unit = scraper._extract_unit_from_text(text)
        if unit:
            # Extract ONLY the unit part from the returned string (e.g., "500g" -> "g")
            m = re.search(r'([a-zA-Z]+)', unit)
            return m.group(1).lower() if m else None
    return None


def _normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    if isinstance(value, dict):
        for key in ("name", "slug", "title"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return None


def _resolve_category_id(cursor, product: Dict[str, Any]) -> Optional[int]:
    candidates: List[str] = []

    category = product.get("category")
    if isinstance(category, dict):
        for key in ("slug", "name", "name_en", "name_de"):
            candidate = _normalize_text(category.get(key))
            if candidate:
                candidates.append(candidate)
    else:
        candidate = _normalize_text(category)
        if candidate:
            candidates.append(candidate)

    parent_categories = product.get("parentCategories")
    if isinstance(parent_categories, list):
        for category_entry in parent_categories:
            if isinstance(category_entry, dict):
                for key in ("slug", "name", "name_en", "name_de"):
                    candidate = _normalize_text(category_entry.get(key))
                    if candidate:
                        candidates.append(candidate)

    for candidate in candidates:
        slug = candidate.lower().replace("/", "-").replace(" ", "-")
        cursor.execute(
            """
            SELECT id
            FROM categories
            WHERE lower(slug) = lower(%s)
               OR lower(name_en) = lower(%s)
               OR lower(name_de) = lower(%s)
            LIMIT 1
            """,
            (slug, candidate, candidate),
        )
        row = cursor.fetchone()
        if row:
            return row[0]

    # If no matching category found, create a fallback category using the first candidate
    if candidates:
        fallback = candidates[0]
        slug = fallback.lower().replace("/", "-").replace(" ", "-")
        try:
            cursor.execute(
                "INSERT INTO categories (slug, name_en, name_de, level) VALUES (%s, %s, %s, %s) RETURNING id",
                (slug, fallback, fallback, 1),
            )
            row = cursor.fetchone()
            if row:
                return row[0]
        except Exception:
            # If concurrent insert or other error, try to select again
            cursor.execute(
                "SELECT id FROM categories WHERE lower(slug) = lower(%s) LIMIT 1",
                (slug,),
            )
            row = cursor.fetchone()
            if row:
                return row[0]

    return None


def _resolve_product_candidates(scraper: RealBillaScraper, data: list) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    seen_slugs = set()

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        if not {"price", "name", "slug"}.issubset(item.keys()):
            continue

        resolved = scraper.resolve_nuxt_data(data, idx)
        if not isinstance(resolved, dict):
            continue

        slug = _normalize_text(resolved.get("slug"))
        name = _normalize_text(resolved.get("name"))
        if not slug or not name or slug in seen_slugs:
            continue

        price = _extract_price(resolved)
        if price is None:
            continue

        results.append(resolved)
        seen_slugs.add(slug)

    return results


def _extract_products_for_page(scraper: RealBillaScraper, html: str) -> List[Dict[str, Any]]:
    payload = _get_nuxt_payload(html)
    if not payload:
        return []
    return _resolve_product_candidates(scraper, payload)


def _fetch_page_products(scraper: RealBillaScraper, session: requests.Session, page: int) -> Tuple[int, List[Dict[str, Any]]]:
    url = SEARCH_URL if page == 1 else f"{SEARCH_URL}?page={page}"
    print(f"[BILLA] Fetching page {page}: {url}")
    html = _fetch_html(session, url)
    products = _extract_products_for_page(scraper, html)
    return _get_total_pages(html), products


def _get_all_search_queries() -> List[str]:
    """
    Return a list of broad search queries to capture all Billa products.
    Includes blank search + category/product-type keywords.
    """
    return [
        " ",  # Blank search
        "obst",  # Fruits
        "gemüse",  # Vegetables
        "milch",  # Milk/Dairy
        "fleisch",  # Meat
        "wurst",  # Sausage
        "käse",  # Cheese
        "brot",  # Bread
        "pasta",  # Pasta
        "reis",  # Rice
        "getreide",  # Cereals
        "getränk",  # Beverages
        "bier",  # Beer
        "wein",  # Wine
        "saft",  # Juice
        "kaffee",  # Coffee
        "tee",  # Tea
        "süßigkeiten",  # Sweets/Candy
        "chips",  # Chips/Snacks
        "tiefkühl",  # Frozen
        "haushalt",  # Household
        "kosmetik",  # Cosmetics
        "baby",  # Baby products
        "haustier",  # Pet products
    ]


def _clear_product_graph(cursor) -> None:
    print("[BILLA] Clearing existing products, offers, and price history...")
    cursor.execute("TRUNCATE TABLE price_history, offers, products RESTART IDENTITY CASCADE;")


def _ensure_store(cursor) -> None:
    cursor.execute(
        """
        INSERT INTO stores (store_id, name, website, logo_url, country, api_available, scraping_required, active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (store_id) DO UPDATE SET
            name = EXCLUDED.name,
            website = EXCLUDED.website,
            logo_url = EXCLUDED.logo_url,
            country = EXCLUDED.country,
            api_available = EXCLUDED.api_available,
            scraping_required = EXCLUDED.scraping_required,
            active = EXCLUDED.active
        """,
        (STORE_ID, STORE_NAME, STORE_WEBSITE, STORE_LOGO, "AT", False, True, True),
    )


def _build_product_row(scraper: RealBillaScraper, cursor, product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    slug = _normalize_text(product.get("slug"))
    name = _normalize_text(product.get("name"))
    if not slug or not name:
        return None

    price = _extract_price(product)
    if price is None:
        return None

    image_url = _extract_image(product)
    unit_normalized = _extract_unit(product, scraper)
    size_normalized = _as_float(product.get("amount"))
    # First try classifier by product name to map into our category paths
    name_for_cat = _normalize_text(product.get("name")) or ""
    cat_result = classify_product(name_for_cat)
    category_id = None
    if cat_result and cat_result.get("category_path"):
        # Try to resolve by leaf name to existing categories
        leaf = cat_result["category_path"][-1]
        try:
            cursor.execute(
                "SELECT id FROM categories WHERE lower(name_en)=lower(%s) OR lower(name_de)=lower(%s) LIMIT 1",
                (leaf, leaf),
            )
            r = cursor.fetchone()
            if r:
                category_id = r[0]
        except Exception:
            category_id = None

    # Fallback: try to resolve from product payload category fields or create
    if not category_id:
        category_id = _resolve_category_id(cursor, product)

    brand_name = None
    brand = product.get("brand")
    if isinstance(brand, dict):
        brand_name = _normalize_text(brand.get("name") or brand.get("slug"))
    else:
        brand_name = _normalize_text(brand)

    # Per request: do not import description or article number (sku)
    barcode = None
    # product_url
    product_url = product.get("url")
    if not isinstance(product_url, str) or not product_url.startswith("http"):
        product_url = f"https://shop.billa.at/produkte/{slug}"

    fingerprint = f"billa:{slug}"
    timestamp = _now()

    return {
        "fingerprint": fingerprint,
        "name_de": name,
        "brand": brand_name,
        "category_id": category_id,
        "unit_normalized": unit_normalized,
        "size_normalized": size_normalized,
        "default_image_url": image_url,
        "created_at": timestamp,
        "updated_at": timestamp,
        "offer_price": price,
        "product_url": product_url,
        "slug": slug,
        "store_id": STORE_ID,
    }


def _insert_products(cursor, product_rows: List[Dict[str, Any]]) -> None:
    if not product_rows:
        return

    records = [
        (
            row["fingerprint"],
            row["name_de"],
            row["brand"],
            row["category_id"],
            row["store_id"],
            row["unit_normalized"],
            row["size_normalized"],
            row["default_image_url"],
            row["created_at"],
            row["updated_at"],
        )
        for row in product_rows
    ]

    query = (
        "INSERT INTO products "
        "(fingerprint, name_de, brand, category_id, store_id, unit_normalized, size_normalized, default_image_url, created_at, updated_at) "
        "VALUES %s"
    )

    execute_values(cursor, query, records, page_size=500)


def _insert_offers(cursor, product_rows: List[Dict[str, Any]]) -> None:
    if not product_rows:
        return

    fingerprints = [row["fingerprint"] for row in product_rows]
    cursor.execute(
        "SELECT fingerprint, id FROM products WHERE fingerprint = ANY(%s)",
        (fingerprints,),
    )
    fingerprint_to_id = dict(cursor.fetchall())

    timestamp = _now()
    offer_rows = []
    for row in product_rows:
        product_id = fingerprint_to_id.get(row["fingerprint"])
        if not product_id:
            continue
        offer_rows.append(
            (
                product_id,
                STORE_ID,
                row["offer_price"],
                row["product_url"],
                True,
                timestamp,
                timestamp,
                timestamp,
            )
        )

    if not offer_rows:
        return

    query = (
        "INSERT INTO offers "
        "(product_id, store_id, price, product_url, is_available, last_seen, created_at, updated_at) "
        "VALUES %s "
        "ON CONFLICT (product_id, store_id) DO UPDATE SET "
        "price = EXCLUDED.price, "
        "product_url = EXCLUDED.product_url, "
        "is_available = EXCLUDED.is_available, "
        "last_seen = EXCLUDED.last_seen, "
        "updated_at = EXCLUDED.updated_at"
    )
    execute_values(cursor, query, offer_rows, page_size=500)


def _insert_price_history(cursor, product_rows: List[Dict[str, Any]]) -> None:
    if not product_rows:
        return

    fingerprints = [row["fingerprint"] for row in product_rows]
    cursor.execute(
        "SELECT p.id, o.id, o.price FROM products p JOIN offers o ON p.id = o.product_id WHERE p.fingerprint = ANY(%s)",
        (fingerprints,),
    )
    rows = cursor.fetchall()
    if not rows:
        return

    timestamp = _now()
    history_rows = []
    for prod_id, offer_id, price in rows:
        try:
            price_val = float(price) if price is not None else None
        except Exception:
            price_val = None
        history_rows.append((offer_id, None, price_val, timestamp, 'billa', timestamp))

    execute_values(
        cursor,
        "INSERT INTO price_history (offer_id, old_price, new_price, changed_at, source, recorded_at) VALUES %s",
        history_rows,
        page_size=500,
    )


def scrape_billa_to_postgres(skip_reset: bool = False, search_queries: Optional[List[str]] = None) -> None:
    database_uri = _load_database_uri()
    scraper = RealBillaScraper()
    session = _get_session()

    if search_queries is None:
        search_queries = _get_all_search_queries()

    conn = psycopg2.connect(database_uri)
    conn.autocommit = False

    try:
        with conn.cursor() as cursor:
            _ensure_store(cursor)
            if not skip_reset:
                _clear_product_graph(cursor)
            conn.commit()

            all_products: List[Dict[str, Any]] = []
            seen_fingerprints = set()

            for query_idx, search_term in enumerate(search_queries):
                query_base = SEARCH_URL if search_term == " " else f"https://www.billa.at/suche/{search_term.replace(' ', '%20')}"
                print(f"\n[BILLA] Search {query_idx + 1}/{len(search_queries)}: '{search_term}'")

                try:
                    first_html = _fetch_html(session, query_base, retries=2)
                except Exception as e:
                    print(f"[BILLA] Failed to fetch search for '{search_term}': {e}")
                    continue

                total_pages = _get_total_pages(first_html)
                print(f"[BILLA] Detected {total_pages} pages for '{search_term}'")

                for page in range(1, total_pages + 1):
                    if page == 1:
                        html = first_html
                        products = _extract_products_for_page(scraper, html)
                    else:
                        if search_term == " ":
                            page_url = f"{SEARCH_URL}?page={page}"
                        else:
                            page_url = f"{query_base}?page={page}"

                        try:
                            html = _fetch_html(session, page_url, retries=2)
                            products = _extract_products_for_page(scraper, html)
                        except Exception as e:
                            print(f"[BILLA] Failed to fetch page {page} for '{search_term}': {e}")
                            break

                    if not products:
                        print(f"[BILLA] Page {page} returned no products for '{search_term}'; moving to next search.")
                        break

                    page_rows: List[Dict[str, Any]] = []
                    for product in products:
                        row = _build_product_row(scraper, cursor, product)
                        if not row:
                            continue
                        if row["fingerprint"] in seen_fingerprints:
                            continue
                        seen_fingerprints.add(row["fingerprint"])
                        page_rows.append(row)

                    print(f"[BILLA] Page {page}: {len(page_rows)} new products")
                    all_products.extend(page_rows)

            print(f"[BILLA] Inserting {len(all_products)} products")
            _insert_products(cursor, all_products)
            _insert_offers(cursor, all_products)
            _insert_price_history(cursor, all_products)
            conn.commit()

            print(f"[BILLA] Done. Imported {len(all_products)} products into PostgreSQL.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Scrape BILLA search pages into PostgreSQL.")
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Do not truncate the existing products/offers/price_history tables before import.",
    )
    parser.add_argument(
        "--search",
        type=str,
        help="Comma-separated search queries (e.g., 'milch,fleisch,obst'). If not provided, uses default broad searches.",
    )
    args = parser.parse_args()

    search_queries = None
    if args.search:
        search_queries = [q.strip() for q in args.search.split(",")]

    scrape_billa_to_postgres(skip_reset=args.keep_existing, search_queries=search_queries)


if __name__ == "__main__":
    main()