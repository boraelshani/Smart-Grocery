#!/usr/bin/env python3
"""
Billa catalog scraper — incremental, no truncation.

Writes to the CURRENT (post-migration-001) schema:
  products          fingerprint upsert, sets name + name_de
  product_store     (product_id, store_id) upsert — base_price, unit_price, flags
  offers            discount-rule rows (percentage / fixed / bogo)
  promotions        one per scrape run per store ("Billa Aktionen <date>")
  promotion_targets links (promotion, product, store) for on-sale items
  price_history     records price changes (product_id, store_id columns)

Usage:
  python scripts/billa_sitemap_to_postgres.py            # full incremental run
  python scripts/billa_sitemap_to_postgres.py --workers 12 --batch 500
  python scripts/billa_sitemap_to_postgres.py --limit 200  # test with 200 products
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
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import psycopg2
from psycopg2.extras import execute_values
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from scrapers.real_billa_scraper import RealBillaScraper
    _SCRAPER = RealBillaScraper()
except Exception:
    _SCRAPER = None

# ── Constants ─────────────────────────────────────────────────────────────────
SITEMAP_URL  = "https://www.billa.at/sitemap.xml"
STORE_ID     = "billa"
STORE_NAME   = "BILLA"
STORE_WEBSITE = "https://www.billa.at"
STORE_LOGO   = "https://shop.billa.at/img/logo.png"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-AT,de;q=0.9,en-US;q=0.5",
}

UNIT_MAP = {
    "kilogramm": "kg", "kilogram": "kg",
    "gramm": "g",      "gram": "g",
    "liter": "l",      "litre": "l",
    "milliliter": "ml","millilitre": "ml",
    "zentiliter": "cl",
    "stück": "stk",    "stueck": "stk", "stk": "stk",
    "st": "stk",       "st.": "stk",    "stck": "stk",
    "packung": "pack", "pack": "pack",
    "dose": "dose",    "flasche": "flasche",
    "beutel": "beutel","karton": "karton",
    "paar": "pair",    "pcs": "stk",    "piece": "stk",
}
KNOWN_UNITS = {"kg","g","l","ml","cl","stk","pack","dose","flasche","beutel","karton","pair"}


# ── Helpers ────────────────────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc)

def _today() -> date:
    return date.today()

def _load_uri() -> str:
    load_dotenv()
    uri = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI")
    if not uri:
        raise RuntimeError("DATABASE_URL is not set")
    return uri

def _connect(uri: str) -> psycopg2.extensions.connection:
    return psycopg2.connect(
        uri, connect_timeout=15,
        keepalives=1, keepalives_idle=30,
        keepalives_interval=10, keepalives_count=5,
    )

def _nfc(s: Any) -> str:
    if not isinstance(s, str):
        s = str(s) if s is not None else ""
    return unicodedata.normalize("NFC", s).strip()

def _normalize_unit(raw: Any) -> Optional[str]:
    if not raw:
        return None
    v = _nfc(raw).lower().rstrip(".")
    v = re.sub(r"\s+", " ", v).strip()
    if v in UNIT_MAP:
        return UNIT_MAP[v]
    if v in KNOWN_UNITS:
        return v
    return None

def _normalize_price(raw: Any) -> Optional[float]:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        p = float(raw)
    except (TypeError, ValueError):
        return None
    if p <= 0:
        return None
    # Billa's Nuxt API returns euro prices as floats (2.39) and cent values as
    # whole integers (149 = €1.49). Dividing integer values by 100 converts cents
    # to euros. Float prices like 2.39 are already in euros and stay unchanged.
    if p == int(p):
        p = p / 100.0
    return round(p, 2)

def _extract_amount(product: Dict[str, Any]) -> Optional[float]:
    amt = product.get("amount")
    if amt is None:
        return None
    try:
        return float(str(amt).replace(",", "."))
    except (TypeError, ValueError):
        return None

def _extract_unit(product: Dict[str, Any]) -> Optional[str]:
    for key in ("baseUnitShort", "volumeLabelShort", "baseUnitLong", "volumeLabelLong"):
        u = _normalize_unit(product.get(key))
        if u:
            return u
    # Fallback: scan name
    name = _nfc(product.get("name") or "").lower()
    for token, unit in [("kilogramm","kg"),("gramm","g"),("milliliter","ml"),
                        ("zentiliter","cl"),("liter","l"),("stück","stk"),("pack","pack")]:
        if token in name:
            return unit
    return None

def _extract_image(product: Dict[str, Any]) -> Optional[str]:
    for img in (product.get("images") or []):
        if isinstance(img, str) and img.startswith("http"):
            return img
        if isinstance(img, dict):
            for k in ("url","src","image","imageUrl"):
                v = img.get(k)
                if isinstance(v, str) and v.startswith("http"):
                    return v
    return None

def _extract_price_data(product: Dict[str, Any]) -> Dict[str, Any]:
    """Return base_price, promo_price, unit_price_str, discount_pct, is_preis_gesenkt, has_app_voucher."""
    result: Dict[str, Any] = {
        "base_price": None, "promo_price": None,
        "unit_price_str": None, "discount_pct": None,
        "is_preis_gesenkt": False, "has_app_voucher": False,
    }
    price_obj = product.get("price")
    if not isinstance(price_obj, dict):
        result["base_price"] = _normalize_price(price_obj)
        return result

    regular = price_obj.get("regular")
    if isinstance(regular, dict):
        result["base_price"] = _normalize_price(regular.get("value"))
        promo_raw = regular.get("promotionValue")
        if promo_raw and promo_raw != regular.get("value"):
            result["promo_price"] = _normalize_price(promo_raw)
    elif regular is not None:
        result["base_price"] = _normalize_price(regular)

    # crossed price means original was higher → current is promo
    crossed = _normalize_price(price_obj.get("crossed"))
    if crossed and result["base_price"] and crossed > result["base_price"]:
        result["promo_price"] = result["base_price"]
        result["base_price"] = crossed

    # unit price string (Grundpreis), e.g. "€1.99 / kg"
    for key in ("baseUnitLong", "perStandardizedQuantity", "pricePerUnit"):
        v = price_obj.get(key)
        if v:
            result["unit_price_str"] = str(v)
            break

    # discount percentage
    disc = price_obj.get("discountPercentage") or price_obj.get("discount")
    if disc:
        try:
            result["discount_pct"] = abs(float(disc))
        except (TypeError, ValueError):
            pass

    # Billa-specific flags
    labels = product.get("labels") or product.get("badges") or []
    for label in (labels if isinstance(labels, list) else []):
        txt = (label.get("text") or label.get("name") or str(label)).lower() if isinstance(label, dict) else str(label).lower()
        if "preis gesenkt" in txt or "preisgesenkt" in txt:
            result["is_preis_gesenkt"] = True
        if "app" in txt and ("rabatt" in txt or "voucher" in txt or "angebot" in txt):
            result["has_app_voucher"] = True

    if not result["base_price"]:
        for key in ("value", "basePrice", "salePrice", "currentPrice"):
            v = _normalize_price(price_obj.get(key))
            if v:
                result["base_price"] = v
                break

    return result


# ── Sitemap ────────────────────────────────────────────────────────────────────
def _load_sitemap_urls(session: requests.Session) -> List[str]:
    resp = session.get(SITEMAP_URL, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    locs = re.findall(r"<loc>(.*?)</loc>", resp.text)
    seen: set = set()
    urls = []
    for loc in locs:
        if "/produkte/" not in loc or loc in seen:
            continue
        seen.add(loc)
        urls.append(loc)
    return urls


# ── Per-product fetch & parse ──────────────────────────────────────────────────
def _extract_nuxt_product(html: str, target_slug: str) -> Optional[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NUXT_DATA__")
    if not tag or not tag.string:
        return None
    try:
        data = json.loads(tag.string)
    except json.JSONDecodeError:
        return None

    target = target_slug.strip().lower()
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        if not {"name", "slug", "price"}.issubset(item.keys()):
            continue
        resolved = item
        if _SCRAPER:
            try:
                resolved = _SCRAPER.resolve_nuxt_data(data, idx) or item
            except Exception:
                pass
        if not isinstance(resolved, dict):
            continue
        slug = str(resolved.get("slug") or "").strip().lower()
        if slug == target:
            return resolved
    return None

def _fetch_product(session: requests.Session, url: str, retries: int = 4) -> Optional[Dict[str, Any]]:
    slug = url.rstrip("/").split("/")[-1]
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, headers=HEADERS, timeout=45, allow_redirects=True)
            if resp.status_code in (404, 410):
                return None
            resp.raise_for_status()
            product = _extract_nuxt_product(resp.text, slug)
            if product:
                return product
            if attempt < retries:
                time.sleep(1.5 * attempt)
        except requests.exceptions.Timeout:
            if attempt < retries:
                time.sleep(min(15, 3 * attempt))
        except requests.exceptions.HTTPError:
            if attempt < retries:
                time.sleep(min(10, 2 * attempt))
        except Exception:
            if attempt < retries:
                time.sleep(2)
    return None


# ── Category resolution ────────────────────────────────────────────────────────
class CategoryIndex:
    def __init__(self, rows: List[Tuple]):
        self._map: Dict[str, int] = {}
        for cat_id, slug, name_en, name_de in rows:
            for v in (slug, name_en, name_de):
                if v:
                    key = v.lower().strip()
                    if key not in self._map:
                        self._map[key] = cat_id

    def resolve(self, candidates: Iterable[str]) -> Optional[int]:
        for c in candidates:
            if not c:
                continue
            k = c.lower().strip()
            if k in self._map:
                return self._map[k]
        # Partial match
        for c in candidates:
            if not c:
                continue
            k = c.lower().strip()
            for key, cat_id in self._map.items():
                if (k in key or key in k) and len(k) > 3:
                    return cat_id
        return None

def _cat_candidates(product: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    cat = product.get("category")
    if isinstance(cat, str):
        out.append(cat)
    elif isinstance(cat, dict):
        for k in ("name","slug","name_en","name_de","key"):
            v = cat.get(k)
            if v:
                out.append(str(v))
    parents = product.get("parentCategories") or []
    if isinstance(parents, list):
        for g in parents:
            if isinstance(g, list):
                for item in g:
                    if isinstance(item, dict):
                        for k in ("name","slug","key"):
                            v = item.get(k)
                            if v: out.append(str(v))
            elif isinstance(g, dict):
                for k in ("name","slug","key"):
                    v = g.get(k)
                    if v: out.append(str(v))
    return out


# ── Build row ─────────────────────────────────────────────────────────────────
def _build_row(url: str, product: Dict[str, Any], cat_index: CategoryIndex) -> Optional[Dict[str, Any]]:
    slug = _nfc(product.get("slug") or "")
    name = _nfc(product.get("name") or "")
    if not slug or not name:
        return None

    price_data = _extract_price_data(product)
    if not price_data["base_price"]:
        return None

    brand_raw = product.get("brand")
    brand = None
    if isinstance(brand_raw, dict):
        brand = _nfc(brand_raw.get("name") or brand_raw.get("slug") or "") or None
    elif isinstance(brand_raw, str):
        brand = _nfc(brand_raw) or None

    category_id = cat_index.resolve(_cat_candidates(product))
    unit = _extract_unit(product)
    size = _extract_amount(product)
    image = _extract_image(product)

    product_url = str(product.get("url") or "")
    if not product_url.startswith("http"):
        product_url = f"https://shop.billa.at/produkte/{slug}"

    # Parse unit_price_str → numeric value + unit string
    unit_price_num: Optional[float] = None
    unit_price_unit: Optional[str] = None
    ustr = price_data.get("unit_price_str") or ""
    if ustr:
        m = re.search(r"([\d,\.]+)", ustr)
        if m:
            try:
                unit_price_num = float(m.group(1).replace(",", "."))
            except ValueError:
                pass
        # unit part: e.g. "€1.99 / kg" → "kg"
        um = re.search(r"/\s*([a-zA-Zü]+)", ustr)
        if um:
            unit_price_unit = _normalize_unit(um.group(1)) or um.group(1).lower()

    return {
        "fingerprint": f"billa:{slug}",
        "name": name,
        "name_de": name,
        "brand": brand,
        "category_id": category_id,
        "unit_normalized": unit,
        "size_normalized": size,
        "default_image_url": image,
        "barcode": None,
        # store data
        "product_url": product_url,
        "base_price": price_data["base_price"],
        "promo_price": price_data["promo_price"],
        "unit_price": unit_price_num,
        "unit_price_unit": unit_price_unit,
        "is_preis_gesenkt": price_data["is_preis_gesenkt"],
        "has_app_voucher": price_data["has_app_voucher"],
        "discount_pct": price_data["discount_pct"],
    }


# ── DB writes ──────────────────────────────────────────────────────────────────
def _ensure_store(cursor) -> None:
    cursor.execute("""
        INSERT INTO stores (store_id, name, website, logo_url, country, api_available, scraping_required, active)
        VALUES (%s, %s, %s, %s, 'AT', FALSE, TRUE, TRUE)
        ON CONFLICT (store_id) DO UPDATE SET
            name=EXCLUDED.name, website=EXCLUDED.website,
            logo_url=EXCLUDED.logo_url, active=EXCLUDED.active
    """, (STORE_ID, STORE_NAME, STORE_WEBSITE, STORE_LOGO))


def _upsert_products(cursor, rows: List[Dict]) -> Dict[str, int]:
    """Upsert products; return fingerprint→id map."""
    if not rows:
        return {}
    ts = _now()
    records = [
        (
            r["fingerprint"], r["name"], r["name_de"],
            r["brand"], r["category_id"],
            r["unit_normalized"], r["size_normalized"],
            r["default_image_url"], r["barcode"],
            ts, ts,
        )
        for r in rows
    ]
    execute_values(cursor, """
        INSERT INTO products
            (fingerprint, name, name_de, brand, category_id,
             unit_normalized, size_normalized, default_image_url, barcode,
             created_at, updated_at)
        VALUES %s
        ON CONFLICT (fingerprint) DO UPDATE SET
            name             = EXCLUDED.name,
            name_de          = EXCLUDED.name_de,
            brand            = EXCLUDED.brand,
            category_id      = COALESCE(EXCLUDED.category_id, products.category_id),
            unit_normalized  = COALESCE(EXCLUDED.unit_normalized, products.unit_normalized),
            size_normalized  = COALESCE(EXCLUDED.size_normalized, products.size_normalized),
            default_image_url= COALESCE(EXCLUDED.default_image_url, products.default_image_url),
            updated_at       = EXCLUDED.updated_at
    """, records, page_size=1000)

    fps = [r["fingerprint"] for r in rows]
    cursor.execute("SELECT fingerprint, id FROM products WHERE fingerprint = ANY(%s)", (fps,))
    return dict(cursor.fetchall())


def _upsert_product_store(cursor, rows: List[Dict], fp_to_id: Dict[str, int]) -> Dict[int, float]:
    """Upsert product_store rows; return product_id→old_base_price for price_history."""
    if not rows:
        return {}

    fps = [r["fingerprint"] for r in rows]
    cursor.execute("""
        SELECT ps.product_id, ps.base_price
        FROM product_store ps
        JOIN products p ON p.id = ps.product_id
        WHERE p.fingerprint = ANY(%s) AND ps.store_id = %s
    """, (fps, STORE_ID))
    old_prices: Dict[int, float] = {pid: float(bp) for pid, bp in cursor.fetchall()}

    ts = _now()
    records = []
    for r in rows:
        pid = fp_to_id.get(r["fingerprint"])
        if not pid:
            continue
        # When a promo_price exists it IS the current selling price;
        # store it as base_price and the regular price as was_price.
        current_price = r["promo_price"] if r["promo_price"] else r["base_price"]
        original_price = r["base_price"] if r["promo_price"] else None
        records.append((
            pid, STORE_ID,
            current_price,
            r["unit_price"],
            r["unit_price_unit"],
            True,  # is_available
            r["product_url"],
            ts,    # last_seen
            r["is_preis_gesenkt"],
            False, # immer_billig (Billa doesn't have this concept)
            r["has_app_voucher"],
            original_price,  # was_price
            ts,    # created_at
        ))

    if not records:
        return old_prices

    execute_values(cursor, """
        INSERT INTO product_store
            (product_id, store_id, base_price, unit_price, unit_price_unit,
             is_available, product_url, last_seen,
             is_preis_gesenkt, immer_billig, has_app_voucher,
             was_price, created_at)
        VALUES %s
        ON CONFLICT (product_id, store_id) DO UPDATE SET
            base_price       = EXCLUDED.base_price,
            unit_price       = EXCLUDED.unit_price,
            unit_price_unit  = EXCLUDED.unit_price_unit,
            is_available     = EXCLUDED.is_available,
            product_url      = EXCLUDED.product_url,
            last_seen        = EXCLUDED.last_seen,
            is_preis_gesenkt = EXCLUDED.is_preis_gesenkt,
            immer_billig     = EXCLUDED.immer_billig,
            has_app_voucher  = EXCLUDED.has_app_voucher,
            was_price        = EXCLUDED.was_price
    """, records, page_size=1000)

    return old_prices


def _record_price_history(cursor, rows: List[Dict], fp_to_id: Dict[str, int], old_prices: Dict[int, float]) -> None:
    ts = _now()
    history = []
    for r in rows:
        pid = fp_to_id.get(r["fingerprint"])
        if not pid:
            continue
        new_price = r["base_price"]
        old_price = old_prices.get(pid)
        if old_price is None or abs(new_price - old_price) > 0.001:
            history.append((pid, STORE_ID, old_price, new_price, ts, STORE_ID))

    if not history:
        return
    execute_values(cursor, """
        INSERT INTO price_history (product_id, store_id, old_price, new_price, changed_at, source)
        VALUES %s
    """, history, page_size=1000)


def _upsert_promotions(cursor, rows: List[Dict], fp_to_id: Dict[str, int], promo_id: Optional[int]) -> None:
    if promo_id is None:
        return
    """For every row with a discount, upsert an offer rule and add a promotion_target."""
    # Group by discount_pct to reuse offer rows
    offer_cache: Dict[str, int] = {}  # discount_key → offer_id

    def _get_or_create_offer(discount_pct: Optional[float], is_preis_gesenkt: bool) -> int:
        """Create or find a matching discount offer row."""
        if discount_pct:
            key = f"pct_{round(discount_pct, 1)}"
            name = f"Billa -{round(discount_pct)}% Rabatt"
            disc_type = "percentage"
            disc_val = round(discount_pct, 2)
        elif is_preis_gesenkt:
            key = "preis_gesenkt"
            name = "Billa Preis Gesenkt"
            disc_type = "percentage"
            disc_val = 5.0  # placeholder when we don't know the exact %
        else:
            key = "generic"
            name = "Billa Aktion"
            disc_type = "percentage"
            disc_val = 1.0

        if key in offer_cache:
            return offer_cache[key]

        cursor.execute("""
            INSERT INTO offers (name, description, discount_type, discount_value, min_quantity, is_active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, 1, TRUE, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
        """, (name, name, disc_type, disc_val, _now(), _now()))
        row = cursor.fetchone()
        if not row:
            cursor.execute("SELECT id FROM offers WHERE name = %s LIMIT 1", (name,))
            row = cursor.fetchone()
        offer_id = row[0]
        offer_cache[key] = offer_id
        return offer_id

    targets = []
    for r in rows:
        has_promo = r.get("promo_price") or r.get("discount_pct") or r.get("is_preis_gesenkt")
        if not has_promo:
            continue
        pid = fp_to_id.get(r["fingerprint"])
        if not pid:
            continue
        offer_id = _get_or_create_offer(r.get("discount_pct"), r.get("is_preis_gesenkt", False))
        # Make sure promotion uses this offer (update offer_id on the promotion)
        cursor.execute("UPDATE promotions SET offer_id = %s WHERE id = %s AND offer_id IS NULL",
                       (offer_id, promo_id))
        targets.append((promo_id, pid, STORE_ID, _now()))

    if not targets:
        return

    execute_values(cursor, """
        INSERT INTO promotion_targets (promotion_id, product_id, store_id, created_at)
        VALUES %s
        ON CONFLICT (promotion_id, product_id, store_id) DO NOTHING
    """, targets, page_size=1000)


def _setup_promotion(cursor) -> int:
    """
    Create today's Billa promotion campaign (one per day).
    Returns the promotion id.
    Deactivates yesterday's billa promotions.
    """
    today = _today()
    promo_name = f"Billa Aktionen {today.isoformat()}"

    # Deactivate old billa promotion campaigns (not today's)
    cursor.execute(
        "UPDATE promotions SET is_active = FALSE WHERE name LIKE %s AND name != %s AND is_active = TRUE",
        ("Billa Aktionen %", promo_name)
    )

    cursor.execute("""
        INSERT INTO promotions (name, description, is_active, start_date, end_date, created_at)
        VALUES (%s, 'Auto-generated from Billa scraper', TRUE, %s, NULL, %s)
        RETURNING id
    """, (promo_name, today, _now()))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("SELECT id FROM promotions WHERE name = %s LIMIT 1", (promo_name,))
    r = cursor.fetchone()
    return r[0] if r else None


# ── Main scrape loop ───────────────────────────────────────────────────────────
def scrape_billa(
    workers: int = 10,
    batch: int = 300,
    limit: Optional[int] = None,
) -> None:
    uri = _load_uri()
    session = requests.Session()

    print("[BILLA] Fetching sitemap...")
    urls = _load_sitemap_urls(session)
    print(f"[BILLA] {len(urls):,} product URLs found")

    if limit:
        urls = urls[:limit]
        print(f"[BILLA] Limiting to {limit} products (test mode)")

    conn = _connect(uri)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            _ensure_store(cur)
            cur.execute("SELECT id, slug, name_en, name_de FROM categories")
            cat_rows = cur.fetchall()
            cat_index = CategoryIndex(cat_rows)
            promo_id = _setup_promotion(cur)
            conn.commit()

        total = len(urls)
        done = inserted = updated = skipped = failed = 0

        def _chunks(lst: list, n: int):
            for i in range(0, len(lst), n):
                yield lst[i:i + n]

        for chunk_idx, chunk in enumerate(_chunks(urls, batch)):
            rows_this_chunk: List[Dict] = []
            seen_fps: set = set()

            with ThreadPoolExecutor(max_workers=workers) as pool:
                fut_map = {pool.submit(_fetch_product, session, url): url for url in chunk}
                for fut in as_completed(fut_map):
                    url = fut_map[fut]
                    done += 1
                    try:
                        product = fut.result()
                    except Exception as exc:
                        failed += 1
                        print(f"[BILLA] ERR {url}: {exc}")
                        continue

                    if not product:
                        skipped += 1
                        continue

                    row = _build_row(url, product, cat_index)
                    if not row:
                        skipped += 1
                        continue

                    fp = row["fingerprint"]
                    if fp in seen_fps:
                        continue
                    seen_fps.add(fp)
                    rows_this_chunk.append(row)

                    if done % 250 == 0:
                        print(f"[BILLA] {done}/{total}  inserted={inserted}  updated={updated}  skipped={skipped}  failed={failed}")

            if not rows_this_chunk:
                print(f"[BILLA] Chunk {chunk_idx+1}: no products to persist")
                continue

            # Commit this chunk
            for attempt in range(1, 4):
                try:
                    with conn.cursor() as cur:
                        fp_to_id = _upsert_products(cur, rows_this_chunk)
                        old_prices = _upsert_product_store(cur, rows_this_chunk, fp_to_id)
                        _record_price_history(cur, rows_this_chunk, fp_to_id, old_prices)
                        _upsert_promotions(cur, rows_this_chunk, fp_to_id, promo_id)
                    conn.commit()

                    # Count new vs updated
                    n_new = sum(1 for r in rows_this_chunk
                                if fp_to_id.get(r["fingerprint"]) not in old_prices)
                    inserted += n_new
                    updated += len(rows_this_chunk) - n_new
                    break
                except psycopg2.Error as exc:
                    conn.rollback()
                    if attempt == 3:
                        print(f"[BILLA] Chunk {chunk_idx+1} failed after 3 attempts: {exc}")
                        failed += len(rows_this_chunk)
                    else:
                        time.sleep(2 * attempt)
                        try:
                            conn = _connect(uri)
                            conn.autocommit = False
                        except Exception:
                            pass

            print(f"[BILLA] Chunk {chunk_idx+1}/{(total+batch-1)//batch}: "
                  f"inserted={inserted}  updated={updated}  skipped={skipped}  failed={failed}")

            # Brief cooldown between chunks to avoid hammering Billa
            time.sleep(0.5)

    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()

    print(f"\n[BILLA] DONE — processed={done}  inserted={inserted}  updated={updated}  skipped={skipped}  failed={failed}")


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Billa sitemap → PostgreSQL (product_store schema)")
    p.add_argument("--workers",  type=int, default=10,  help="Concurrent HTTP workers (default 10)")
    p.add_argument("--batch",    type=int, default=300, help="Commit every N products (default 300)")
    p.add_argument("--limit",    type=int, default=None,help="Stop after N products (for testing)")
    args = p.parse_args()
    scrape_billa(workers=args.workers, batch=args.batch, limit=args.limit)


if __name__ == "__main__":
    main()
