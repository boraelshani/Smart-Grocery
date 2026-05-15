#!/usr/bin/env python3
"""Scrape the full BILLA catalog from the sitemap and load it into PostgreSQL.

This importer uses the public BILLA sitemap to enumerate all product URLs, then
fetches each product page and extracts the resolved Nuxt product object.

Behavior:
- truncates products, offers, and price_history by default
- never creates or mutates categories
- maps product categories only to existing category rows when possible
- normalizes unit_normalized to unit-only values like kg, g, l, ml, stk, cl
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import execute_values
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from scrapers.real_billa_scraper import RealBillaScraper

SITEMAP_URL = "https://www.billa.at/sitemap.xml"
STORE_ID = "billa"
STORE_NAME = "BILLA"
STORE_WEBSITE = "https://www.billa.at"
STORE_LOGO = "https://shop.billa.at/img/logo.png"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
}
UNIT_ALIASES = {
    "kilogramm": "kg",
    "kilogram": "kg",
    "gramm": "g",
    "gram": "g",
    "liter": "l",
    "litre": "l",
    "milliliter": "ml",
    "millilitre": "ml",
    "zentiliter": "cl",
    "stück": "stk",
    "stueck": "stk",
    "stk": "stk",
    "st": "stk",
    "st.": "stk",
    "packung": "pack",
    "pack": "pack",
    "dose": "dose",
    "flasche": "flasche",
    "beutel": "beutel",
    "karton": "karton",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_database_uri() -> str:
    load_dotenv()
    database_uri = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI")
    if not database_uri:
        raise RuntimeError("DATABASE_URL or SQLALCHEMY_DATABASE_URI is not set.")
    return database_uri


def _connect_db(database_uri: str):
    return psycopg2.connect(
        database_uri,
        connect_timeout=15,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _normalize_unit(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    cleaned = unicodedata.normalize("NFKD", value)
    cleaned = "".join(ch for ch in cleaned if not unicodedata.combining(ch))
    cleaned = cleaned.lower().strip().replace(".", "")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip()
    if not cleaned:
        return None
    if cleaned in UNIT_ALIASES:
        return UNIT_ALIASES[cleaned]
    compact = cleaned.replace(" ", "")
    if compact in UNIT_ALIASES:
        return UNIT_ALIASES[compact]
    if cleaned in {"kg", "g", "l", "ml", "cl", "stk", "pack", "dose", "flasche", "beutel", "karton"}:
        return cleaned
    return None


def _normalize_price(raw_price: Any) -> Optional[float]:
    if raw_price is None or isinstance(raw_price, bool):
        return None
    try:
        price = float(raw_price)
    except (TypeError, ValueError):
        return None
    if price <= 0:
        return None
    if float(price).is_integer():
        price = price / 100.0
    return round(price, 2)


def _extract_price_data(product: Dict[str, Any]) -> Dict[str, Any]:
    """Extract comprehensive price and offer data from product."""
    price_obj = product.get("price")
    result = {
        "base_price": None,
        "promo_price": None,
        "unit_price": None,
        "offer_details": None,
        "min_quantity": None,
    }
    
    if not isinstance(price_obj, dict):
        price = _normalize_price(price_obj)
        if price:
            result["base_price"] = price
        return result
    
    # Extract regular/base price
    regular = price_obj.get("regular")
    if isinstance(regular, dict):
        base_val = regular.get("value")
        promo_val = regular.get("promotionValue")
        result["base_price"] = _normalize_price(base_val)
        if promo_val and promo_val != base_val:
            result["promo_price"] = _normalize_price(promo_val)
    elif regular is not None:
        result["base_price"] = _normalize_price(regular)
    
    # Check for crossed/original price (indicates discount)
    crossed = price_obj.get("crossed")
    if crossed:
        crossed_price = _normalize_price(crossed)
        if crossed_price and not result["base_price"]:
            result["base_price"] = crossed_price
        elif crossed_price and result["base_price"] and crossed_price > result["base_price"]:
            # Crossed price is higher, so current price is promo
            result["promo_price"] = result["base_price"]
            result["base_price"] = crossed_price
    
    # Extract unit price (e.g., "€1.99/kg")
    unit_price_obj = price_obj.get("baseUnitLong") or price_obj.get("perStandardizedQuantity")
    if unit_price_obj:
        result["unit_price"] = str(unit_price_obj)
    
    # Extract discount percentage
    discount_pct = price_obj.get("discountPercentage")
    if discount_pct:
        result["offer_details"] = f"-{abs(int(discount_pct))}%"
    
    # Check for quantity-based offers (e.g., "ab 24 Stück")
    min_qty = price_obj.get("minQuantity") or price_obj.get("minimumQuantity")
    if min_qty:
        try:
            result["min_quantity"] = int(min_qty)
        except (TypeError, ValueError):
            pass
    
    # Extract offer labels/badges
    labels = product.get("labels") or product.get("badges") or []
    if isinstance(labels, list):
        for label in labels:
            if isinstance(label, dict):
                label_text = label.get("text") or label.get("name") or ""
            else:
                label_text = str(label)
            
            if label_text:
                # Look for offer patterns
                if any(x in label_text.lower() for x in ["aktion", "angebot", "rabatt", "gratis", "+"]):
                    if result["offer_details"]:
                        result["offer_details"] += f" | {label_text}"
                    else:
                        result["offer_details"] = label_text
    
    # If no base price found, try other fields
    if not result["base_price"]:
        for key in ("value", "basePrice", "salePrice"):
            val = price_obj.get(key)
            if val:
                result["base_price"] = _normalize_price(val)
                if result["base_price"]:
                    break
    
    return result


def _extract_price(product: Dict[str, Any]) -> Optional[float]:
    """Legacy function for backward compatibility - returns effective price."""
    price_data = _extract_price_data(product)
    return price_data.get("promo_price") or price_data.get("base_price")


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


def _extract_unit(product: Dict[str, Any]) -> Optional[str]:
    # Prefer the dedicated unit fields from the product object.
    for key in ("baseUnitShort", "volumeLabelShort"):
        unit = _normalize_unit(product.get(key))
        if unit:
            return unit

    # Then try the long unit labels.
    for key in ("baseUnitLong", "volumeLabelLong"):
        unit = _normalize_unit(product.get(key))
        if unit:
            return unit

    # Fallback: sometimes the unit appears in the product label fields.
    text_candidates = [
        product.get("name") or "",
        product.get("descriptionShort") or "",
        product.get("descriptionLong") or "",
    ]
    for text in text_candidates:
        txt = _normalize_text(text)
        if not txt:
            continue
        if any(token in txt for token in ["kilogramm", "kilogram"]):
            return "kg"
        if any(token in txt for token in ["milliliter", "millilitre"]):
            return "ml"
        if "zentiliter" in txt:
            return "cl"
        if any(token in txt for token in ["liter", "litre"]):
            return "l"
        if any(token in txt for token in ["gramm", "gram"]):
            return "g"
        if any(token in txt for token in ["stueck", "stück", "stk"]):
            return "stk"
        if "pack" in txt:
            return "pack"
    return None


def _extract_amount(product: Dict[str, Any]) -> Optional[float]:
    amount = product.get("amount")
    if amount is None:
        return None
    try:
        return float(str(amount).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _load_sitemap_product_urls(session: requests.Session) -> List[str]:
    response = session.get(SITEMAP_URL, timeout=60)
    response.raise_for_status()
    locs = re.findall(r"<loc>(.*?)</loc>", response.text)
    urls = []
    seen = set()
    for loc in locs:
        if "/produkte/" not in loc:
            continue
        if loc in seen:
            continue
        seen.add(loc)
        urls.append(loc)
    return urls


def _chunked(values: Sequence[str], size: int) -> Iterable[List[str]]:
    for start in range(0, len(values), size):
        yield list(values[start : start + size])


def _fingerprint_from_url(product_url: str) -> str:
    slug = product_url.rstrip("/").split("/")[-1]
    return f"billa:{slug}"


def _get_category_rows(cursor) -> List[Dict[str, Any]]:
    cursor.execute("SELECT id, slug, name_en, name_de, parent_id FROM categories")
    rows = cursor.fetchall()
    return [
        {"id": r[0], "slug": r[1], "name_en": r[2], "name_de": r[3], "parent_id": r[4]}
        for r in rows
    ]


class CategoryIndex:
    def __init__(self, rows: Sequence[Dict[str, Any]]):
        self.rows = list(rows)
        self.by_key: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in self.rows:
            for value in (row.get("slug"), row.get("name_en"), row.get("name_de")):
                key = _normalize_text(value)
                if key:
                    self.by_key[key].append(row)
        self.keys = list(self.by_key.keys())

    def resolve(self, candidate_texts: Iterable[str]) -> Optional[int]:
        normalized_candidates = [k for k in (_normalize_text(text) for text in candidate_texts) if k]
        if not normalized_candidates:
            return None

        # Exact matches first.
        for candidate in normalized_candidates:
            matches = self.by_key.get(candidate)
            if matches:
                return matches[0]["id"]

        # Partial matches next. Choose the most specific existing category.
        best_match = None
        best_score = 0
        for candidate in normalized_candidates:
            for key in self.keys:
                if candidate == key:
                    continue
                if candidate in key or key in candidate:
                    score = min(len(candidate), len(key))
                    if score > best_score:
                        best_score = score
                        best_match = self.by_key[key][0]["id"]
        return best_match


CATEGORY_FALLBACKS = [
    ["Obst & Gemüse", "Obst", "Exotisches Obst"],
    ["Obst & Gemüse", "Obst"],
    ["Obst & Gemüse", "Gemüse"],
    ["Dairy & Eggs", "Milk"],
    ["Dairy & Eggs", "Cheese"],
    ["Dairy & Eggs", "Eggs"],
    ["Dairy & Eggs", "Butter & Cream"],
    ["Meat & Fish", "Fresh Meat"],
    ["Meat & Fish", "Sausages & Cold Cuts"],
    ["Bakery & Bread", "Bread"],
    ["Bakery & Bread", "Rolls & Buns"],
    ["Pantry & Staples", "Pasta & Rice"],
    ["Pantry & Staples", "Sauces & Condiments"],
    ["Pantry & Staples", "Canned & Jarred Goods"],
    ["Beverages", "Water"],
    ["Beverages", "Soft Drinks"],
    ["Beverages", "Juice & Nectar"],
    ["Beverages", "Coffee"],
    ["Beverages", "Tea"],
    ["Snacks & Sweets", "Chips"],
    ["Snacks & Sweets", "Sweets"],
    ["Frozen", "Frozen Pizza"],
    ["Frozen", "Frozen Ready Meals"],
    ["Household & Personal Care", "Cleaning"],
    ["Baby & Kids", "Baby Food"],
    ["Pets", "Pet Food"],
]


def _resolve_category_id(category_index: CategoryIndex, product: Dict[str, Any]) -> Optional[int]:
    candidate_texts: List[str] = []

    # Product category + breadcrumb categories from Billa.
    category = product.get("category")
    if isinstance(category, str):
        candidate_texts.append(category)
    elif isinstance(category, dict):
        candidate_texts.extend(
            [
                category.get("name") or "",
                category.get("slug") or "",
                category.get("name_en") or "",
                category.get("name_de") or "",
            ]
        )

    parent_categories = product.get("parentCategories")
    if isinstance(parent_categories, list):
        for group in parent_categories:
            if isinstance(group, list):
                for cat in group:
                    if isinstance(cat, dict):
                        candidate_texts.extend(
                            [
                                cat.get("name") or "",
                                cat.get("slug") or "",
                                cat.get("key") or "",
                            ]
                        )
            elif isinstance(group, dict):
                candidate_texts.extend(
                    [
                        group.get("name") or "",
                        group.get("slug") or "",
                        group.get("key") or "",
                    ]
                )

    # Try direct + partial match against existing categories.
    category_id = category_index.resolve(candidate_texts)
    if category_id:
        return category_id

    # Try fallbacks from the known taxonomy labels, but still only map to existing rows.
    for path in CATEGORY_FALLBACKS:
        category_id = category_index.resolve(path)
        if category_id:
            return category_id
    return None


def _extract_resolved_product(html: str, target_slug: str) -> Optional[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NUXT_DATA__")
    if not script or not script.string:
        return None

    try:
        data = json.loads(script.string)
    except json.JSONDecodeError:
        return None

    scraper = RealBillaScraper()
    target = target_slug.strip().lower()

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        if not {"name", "slug", "price"}.issubset(item.keys()):
            continue
        resolved = scraper.resolve_nuxt_data(data, idx)
        if not isinstance(resolved, dict):
            continue
        slug = str(resolved.get("slug") or "").strip().lower()
        if slug == target:
            return resolved

    return None


def _fetch_product(session: requests.Session, url: str, retries: int = 5) -> Optional[Dict[str, Any]]:
    slug = url.rstrip("/").split("/")[-1]
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, headers=HEADERS, timeout=60, allow_redirects=True)
            response.raise_for_status()
            product = _extract_resolved_product(response.text, slug)
            if product:
                return product
            # If no product found, it might be a redirect or removed product
            if attempt < retries:
                time.sleep(min(8, attempt * 2))
                continue
            return None
        except requests.exceptions.Timeout as exc:
            last_error = exc
            if attempt < retries:
                print(f"[BILLA] Timeout on {url}, retry {attempt}/{retries}")
                time.sleep(min(10, attempt * 3))
        except requests.exceptions.HTTPError as exc:
            # 404 or 410 means product no longer exists
            if exc.response.status_code in (404, 410):
                return None
            last_error = exc
            if attempt < retries:
                time.sleep(min(8, attempt * 2))
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(8, attempt * 2))
    
    print(f"[BILLA] Failed to fetch {url} after {retries} attempts: {last_error}")
    return None


def _build_product_row(category_index: CategoryIndex, product_url: str, product: Dict[str, Any]) -> Dict[str, Any]:
    slug = str(product.get("slug") or "").strip()
    name = str(product.get("name") or "").strip()
    price_data = _extract_price_data(product)
    
    # Need at least a base price
    if not slug or not name or not price_data.get("base_price"):
        return {}

    brand = product.get("brand")
    brand_name = None
    if isinstance(brand, dict):
        brand_name = str(brand.get("name") or brand.get("slug") or "").strip() or None
    elif isinstance(brand, str):
        brand_name = brand.strip() or None

    category_id = _resolve_category_id(category_index, product)
    unit_normalized = _extract_unit(product)
    amount = _extract_amount(product)
    image_url = _extract_image(product)

    return {
        "fingerprint": f"billa:{slug}",
        "name_de": name,
        "brand": brand_name,
        "category_id": category_id,
        "store_id": STORE_ID,
        "unit_normalized": unit_normalized,
        "size_normalized": amount,
        "default_image_url": image_url,
        "barcode": None,
        "created_at": _now(),
        "updated_at": _now(),
        "product_url": product_url,
        # Offer data
        "base_price": price_data["base_price"],
        "promo_price": price_data["promo_price"],
        "unit_price": price_data["unit_price"],
        "offer_details": price_data["offer_details"],
        "min_quantity": price_data["min_quantity"],
    }


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


def _insert_products(cursor, rows: List[Dict[str, Any]], update_mode: str = 'full') -> None:
    """Insert or update products.
    
    Args:
        update_mode: 'full' = update all fields, 'minimal' = only update updated_at
    """
    if not rows:
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
            row["barcode"],
            row["created_at"],
            row["updated_at"],
        )
        for row in rows
    ]
    
    if update_mode == 'minimal':
        # Only update timestamp for existing products (price-only updates)
        execute_values(
            cursor,
            """INSERT INTO products (fingerprint, name_de, brand, category_id, store_id, unit_normalized, size_normalized, default_image_url, barcode, created_at, updated_at) 
            VALUES %s 
            ON CONFLICT (fingerprint) DO UPDATE SET updated_at = EXCLUDED.updated_at""",
            records,
            page_size=1000,
        )
    else:
        # Full update for new products or changed products
        execute_values(
            cursor,
            """INSERT INTO products (fingerprint, name_de, brand, category_id, store_id, unit_normalized, size_normalized, default_image_url, barcode, created_at, updated_at) 
            VALUES %s 
            ON CONFLICT (fingerprint) DO UPDATE SET 
                name_de = EXCLUDED.name_de, 
                brand = EXCLUDED.brand, 
                category_id = EXCLUDED.category_id, 
                store_id = EXCLUDED.store_id, 
                unit_normalized = EXCLUDED.unit_normalized, 
                size_normalized = EXCLUDED.size_normalized, 
                default_image_url = EXCLUDED.default_image_url, 
                barcode = EXCLUDED.barcode, 
                updated_at = EXCLUDED.updated_at""",
            records,
            page_size=1000,
        )


def _insert_offers(cursor, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    fingerprints = [row["fingerprint"] for row in rows]
    cursor.execute("SELECT fingerprint, id FROM products WHERE fingerprint = ANY(%s)", (fingerprints,))
    fp_to_id = dict(cursor.fetchall())

    offer_rows = []
    ts = _now()
    for row in rows:
        product_id = fp_to_id.get(row["fingerprint"])
        if not product_id:
            continue
        
        # Use base_price for legacy price field, but store both base and promo
        base_price = row.get("base_price")
        promo_price = row.get("promo_price")
        
        offer_rows.append(
            (
                product_id,
                STORE_ID,
                base_price,  # Legacy price field
                base_price,  # base_price
                promo_price,  # promo_price
                row.get("unit_price"),
                row.get("offer_details"),
                row.get("min_quantity"),
                row["product_url"],
                True,
                ts,
                ts,
                ts,
            )
        )

    if not offer_rows:
        return

    execute_values(
        cursor,
        """INSERT INTO offers (product_id, store_id, price, base_price, promo_price, unit_price, offer_details, min_quantity, product_url, is_available, last_seen, created_at, updated_at) 
        VALUES %s 
        ON CONFLICT (product_id, store_id) DO UPDATE SET 
            price=EXCLUDED.price, 
            base_price=EXCLUDED.base_price, 
            promo_price=EXCLUDED.promo_price, 
            unit_price=EXCLUDED.unit_price, 
            offer_details=EXCLUDED.offer_details, 
            min_quantity=EXCLUDED.min_quantity, 
            product_url=EXCLUDED.product_url, 
            is_available=EXCLUDED.is_available, 
            last_seen=EXCLUDED.last_seen, 
            updated_at=EXCLUDED.updated_at""",
        offer_rows,
        page_size=1000,
    )


def _insert_price_history(cursor, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    fingerprints = [row["fingerprint"] for row in rows]
    cursor.execute(
        "SELECT p.id, o.id, o.base_price, o.promo_price FROM products p JOIN offers o ON p.id = o.product_id WHERE p.fingerprint = ANY(%s)",
        (fingerprints,)
    )
    data = cursor.fetchall()
    if not data:
        return

    offer_ids = [offer_id for _product_id, offer_id, _base, _promo in data]
    cursor.execute(
        "SELECT offer_id FROM price_history WHERE offer_id = ANY(%s) AND source = %s",
        (offer_ids, STORE_ID),
    )
    existing_offer_ids = {row[0] for row in cursor.fetchall()}

    ts = _now()
    history_rows = []
    for _product_id, offer_id, base_price, promo_price in data:
        if offer_id in existing_offer_ids:
            continue
        # Record the effective price (promo if available, otherwise base)
        effective_price = promo_price if promo_price else base_price
        history_rows.append((offer_id, None, float(effective_price) if effective_price is not None else None, ts, STORE_ID))
    
    if history_rows:
        execute_values(
            cursor,
            "INSERT INTO price_history (offer_id, old_price, new_price, changed_at, source) VALUES %s",
            history_rows,
            page_size=1000,
        )


def _row_persisted(database_uri: str, fingerprint: str) -> bool:
    check_conn = _connect_db(database_uri)
    try:
        with check_conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.id, o.id
                FROM products p
                JOIN offers o ON o.product_id = p.id
                WHERE p.fingerprint = %s AND o.store_id = %s
                """,
                (fingerprint, STORE_ID),
            )
            return cursor.fetchone() is not None
    finally:
        check_conn.close()


def _persist_rows(conn, rows: List[Dict[str, Any]], database_uri: str, update_mode: str = 'full') -> psycopg2.extensions.connection:
    """Persist product and offer data.
    
    Args:
        update_mode: 'full' = new product, 'minimal' = price/offer update only
    """
    if not rows:
        return conn

    fingerprint = rows[0]["fingerprint"]
    for attempt in range(1, 4):
        try:
            with conn.cursor() as cursor:
                _insert_products(cursor, rows, update_mode=update_mode)
                _insert_offers(cursor, rows)
                # Only insert price history for actual price changes
                if update_mode == 'full' or any(row.get('price_changed') for row in rows):
                    _insert_price_history(cursor, rows)
                conn.commit()
            return conn
        except psycopg2.Error:
            try:
                if conn.closed == 0:
                    conn.rollback()
            except Exception:
                pass

            try:
                if _row_persisted(database_uri, fingerprint):
                    return conn
            except psycopg2.Error:
                # If verification cannot reach DB, continue with reconnect/retry.
                pass

            try:
                conn.close()
            except Exception:
                pass
            if attempt == 3:
                raise
            time.sleep(min(5, attempt * 2))
            conn = _connect_db(database_uri)
            conn.autocommit = False

    return conn


def _load_existing_products(cursor) -> Dict[str, Dict[str, Any]]:
    """Load existing products with their current offer data for comparison."""
    cursor.execute("""
        SELECT 
            p.fingerprint,
            p.id,
            p.name_de,
            o.base_price,
            o.promo_price,
            o.unit_price,
            o.offer_details,
            o.min_quantity
        FROM products p
        LEFT JOIN offers o ON p.id = o.product_id AND o.store_id = %s
        WHERE p.store_id = %s
    """, (STORE_ID, STORE_ID))
    
    result = {}
    for row in cursor.fetchall():
        fingerprint, prod_id, name, base_price, promo_price, unit_price, offer_details, min_qty = row
        result[fingerprint] = {
            'id': prod_id,
            'name': name,
            'base_price': float(base_price) if base_price else None,
            'promo_price': float(promo_price) if promo_price else None,
            'unit_price': unit_price,
            'offer_details': offer_details,
            'min_quantity': min_qty,
        }
    return result


def scrape_billa_to_postgres(
    workers: int = 8,
    chunk_size: int = 300,
    resume: bool = False,
    shard_count: int = 1,
    shard_index: int = 0,
) -> None:
    database_uri = _load_database_uri()
    session = requests.Session()
    session.headers.update(HEADERS)

    print("[BILLA] Loading sitemap product URLs...")
    product_urls = _load_sitemap_product_urls(session)
    print(f"[BILLA] Found {len(product_urls):,} product URLs in sitemap")

    conn = _connect_db(database_uri)
    conn.autocommit = False
    try:
        with conn.cursor() as cursor:
            _ensure_store(cursor)
            if not resume:
                _clear_product_graph(cursor)
            category_rows = _get_category_rows(cursor)
            category_index = CategoryIndex(category_rows)
            existing_products = _load_existing_products(cursor) if resume else {}
            conn.commit()

        # In resume mode, we still need to check ALL products for price/offer updates
        # But we'll handle them differently based on whether they exist
        if resume and existing_products:
            print(f"[BILLA] Resume mode: {len(existing_products):,} existing products will be checked for updates")

        if shard_count > 1:
            if shard_index < 0 or shard_index >= shard_count:
                raise ValueError("shard-index must be between 0 and shard-count - 1")
            product_urls = [
                url for index, url in enumerate(product_urls) if index % shard_count == shard_index
            ]
            print(
                f"[BILLA] Shard {shard_index + 1}/{shard_count}: {len(product_urls):,} URLs assigned"
            )

        total = len(product_urls)
        processed = 0
        inserted = 0
        updated = 0
        skipped = 0
        failed = 0

        print(f"[BILLA] Fetching product pages with {workers} workers in batches of {chunk_size}...")
        for batch_idx, batch in enumerate(_chunked(product_urls, chunk_size)):
            batch_rows: List[Dict[str, Any]] = []
            seen = set()

            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {executor.submit(_fetch_product, session, url): url for url in batch}
                for future in as_completed(future_map):
                    url = future_map[future]
                    processed += 1
                    try:
                        product = future.result()
                    except Exception as exc:
                        print(f"[BILLA] {processed}/{total} exception for {url}: {exc}")
                        failed += 1
                        continue

                    if not product:
                        skipped += 1
                        if processed % 500 == 0:
                            print(f"[BILLA] Progress: {processed}/{total} | New: {inserted} | Updated: {updated} | Skipped: {skipped} | Failed: {failed}")
                        continue

                    row = _build_product_row(category_index, url, product)
                    if not row:
                        skipped += 1
                        continue
                    
                    fingerprint = row["fingerprint"]
                    if fingerprint in seen:
                        skipped += 1
                        continue
                    seen.add(fingerprint)
                    
                    # Check if product exists and needs update
                    existing = existing_products.get(fingerprint)
                    
                    if existing:
                        # Product exists - check if we need to update
                        needs_update = False
                        price_changed = False
                        
                        # Check if price changed
                        new_base = row.get("base_price")
                        new_promo = row.get("promo_price")
                        old_base = existing.get("base_price")
                        old_promo = existing.get("promo_price")
                        
                        if new_base != old_base or new_promo != old_promo:
                            needs_update = True
                            price_changed = True
                        
                        # Check if offer details changed (promotions, unit price, etc.)
                        if (row.get("offer_details") != existing.get("offer_details") or
                            row.get("unit_price") != existing.get("unit_price") or
                            row.get("min_quantity") != existing.get("min_quantity")):
                            needs_update = True
                        
                        if needs_update:
                            # Update only offer data, not full product
                            row['price_changed'] = price_changed
                            conn = _persist_rows(conn, [row], database_uri, update_mode='minimal')
                            updated += 1
                            if processed % 500 == 0:
                                print(f"[BILLA] Progress: {processed}/{total} | New: {inserted} | Updated: {updated} | Skipped: {skipped} | Failed: {failed}")
                        else:
                            # No changes needed
                            skipped += 1
                    else:
                        # New product - full insert
                        batch_rows.append(row)
                        conn = _persist_rows(conn, [row], database_uri, update_mode='full')
                        inserted += 1
                        existing_products[fingerprint] = {
                            'base_price': row.get("base_price"),
                            'promo_price': row.get("promo_price"),
                            'unit_price': row.get("unit_price"),
                            'offer_details': row.get("offer_details"),
                            'min_quantity': row.get("min_quantity"),
                        }
                        batch_rows.clear()

                        if processed % 500 == 0:
                            print(f"[BILLA] Progress: {processed}/{total} | New: {inserted} | Updated: {updated} | Skipped: {skipped} | Failed: {failed}")

            if batch_rows:
                conn = _persist_rows(conn, batch_rows, database_uri, update_mode='full')
                inserted += len(batch_rows)
                for row in batch_rows:
                    existing_products[row["fingerprint"]] = {
                        'base_price': row.get("base_price"),
                        'promo_price': row.get("promo_price"),
                        'unit_price': row.get("unit_price"),
                        'offer_details': row.get("offer_details"),
                        'min_quantity': row.get("min_quantity"),
                    }
                batch_rows.clear()

            print(f"[BILLA] Batch {batch_idx + 1} complete: New={inserted:,} | Updated={updated:,} | Skipped={skipped:,} | Failed={failed}")

        print(f"[BILLA] Done. New products: {inserted:,} | Updated: {updated:,}")
        print(f"[BILLA] Summary: Processed={processed}, New={inserted}, Updated={updated}, Skipped={skipped}, Failed={failed}")
    except Exception:
        if conn.closed == 0:
            conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Scrape full BILLA catalog from sitemap into PostgreSQL.")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent product-page fetch workers.")
    parser.add_argument("--chunk-size", type=int, default=300, help="How many product URLs to process before each commit.")
    parser.add_argument("--resume", action="store_true", help="Keep existing rows and skip fingerprints already in PostgreSQL.")
    parser.add_argument("--shard-count", type=int, default=1, help="Split remaining URLs across N parallel importer processes.")
    parser.add_argument("--shard-index", type=int, default=0, help="Zero-based shard index for this process.")
    args = parser.parse_args()

    scrape_billa_to_postgres(
        workers=max(1, args.workers),
        chunk_size=max(1, args.chunk_size),
        resume=args.resume,
        shard_count=max(1, args.shard_count),
        shard_index=max(0, args.shard_index),
    )


if __name__ == "__main__":
    main()
