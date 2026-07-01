"""
SPAR Austria Scraper — Direct API Method
=========================================
SPAR's search page calls an internal JSON API at api-scp.spar-ics.com which
returns all product data including prices, promo prices, and offer text.

The API requires Cloudflare-cleared session cookies, so we:
  1. Open one browser session to load the SPAR search page (establishes cookies)
  2. Intercept the first API call to discover the exact URL + query params
  3. Use page.evaluate(fetch(...)) for all subsequent pages — the browser handles
     auth cookies automatically, but we skip full page navigation
  4. Parse the JSON response directly — no DOM scraping at all

API fields used:
  masterValues.name1                    brand (e.g. "SPAR", "Ja! Natürlich")
  masterValues.name2                    product name
  masterValues.name3                    size/quantity (e.g. "480 ML")
  masterValues.slug                     URL slug
  masterValues.productId                SPAR internal ID (NOT an EAN barcode)
  masterValues.productImage_assetUrl    CDN image URL template
  geoValues.calculatedPrice             current price (promo price if on sale)
  geoValues.basePrice                   regular shelf price
  geoValues.stattPrice                  "was" price on promo badge
  geoValues.inAngebot                   True when on promotion
  geoValues.promotionBadgeText          e.g. "2+1 GRATIS - ab 3 Stk. je"
  geoValues.hasAktionsPrice             True when promo price applies
  geoValues.comparisonPrice_price       per-unit price (Grundpreis)
  geoValues.comparisonPrice_quantity    reference quantity for Grundpreis
  geoValues.comparisonPrice_unit        unit for Grundpreis (l, kg, stk, …)
  geoValues.isPreisGesenkt              permanent price reduction (not a promo)
  geoValues.immerBillig                 SPAR budget tier product
  geoValues.mengenRabatt                quantity discount available
  geoValues.hasAppVoucher               app-exclusive voucher available
"""

import re
import time
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    raise SystemExit(
        "[!] Playwright not installed. Run: pip install playwright && playwright install chromium"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Field helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_decimal(val) -> Optional[Decimal]:
    try:
        return Decimal(str(float(val)))
    except (TypeError, ValueError):
        return None


def _parse_date_de(text: str) -> Optional[datetime]:
    """Parse German date text like 'bis 31.12.2024'."""
    if not text:
        return None
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", str(text))
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)), tzinfo=timezone.utc)
        except ValueError:
            return None
    if "woche" in str(text).lower():
        today = datetime.now(timezone.utc)
        return today + timedelta(days=(6 - today.weekday()) % 7)
    return None


def _extract_unit(text: str) -> Tuple[Optional[str], Optional[float]]:
    """Extract unit type and normalized size from product name/size string."""
    if not text:
        return None, None
    t = str(text).lower().replace(",", ".")
    m = re.search(r"(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(kg|g|l|ml|stk|stück)", t)
    if m:
        unit = "stk" if m.group(3) == "stück" else m.group(3)
        return unit, float(m.group(1)) * float(m.group(2))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(kg|g|l|ml|stk|stück)", t)
    if m:
        unit = "stk" if m.group(2) == "stück" else m.group(2)
        return unit, float(m.group(1))
    return None, None


def _fingerprint(name: str, brand: str, unit: str, size: Optional[float]) -> str:
    """Stable deduplication key for a product (store-independent)."""
    n = re.sub(r"[^\w\s]", "", (name or "").lower()).strip()
    b = re.sub(r"[^\w\s]", "", (brand or "").lower()).strip()
    u = (unit or "").lower()
    s = f"{size:.2f}" if size else ""
    return "_".join(p for p in [b, n, s, u] if p)


def _image_url(asset_url: str, size: int = 500) -> Optional[str]:
    """Expand SPAR CDN image URL template (replaces {size} and {ext})."""
    if not asset_url:
        return None
    url = asset_url.replace("{size}", str(size)).replace("{ext}", "jpg")
    if not url.startswith("http"):
        url = ("https:" if url.startswith("//") else "https://cdn1.interspar.at") + url
    return url


# ─────────────────────────────────────────────────────────────────────────────
# Scraper
# ─────────────────────────────────────────────────────────────────────────────

class SparDirectScraper:
    """
    Scrapes SPAR Austria via their internal search API using an in-browser
    fetch() call for each page. Pagination is driven by the API's page parameter.
    No DOM parsing — all data comes from the JSON response.
    """

    BASE_URL = "https://www.spar.at"
    STORE_ID = "spar"
    SEARCH_URL = "https://www.spar.at/produktwelt/suche"
    API_HOST = "api-scp.spar-ics.com"

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._api_url: Optional[str] = None  # discovered on first load

        self.stats = {
            "pages_fetched": 0,
            "products_extracted": 0,
            "products_added": 0,
            "products_updated": 0,
            "promotions_added": 0,
            "errors": 0,
        }

    # ── Browser lifecycle ────────────────────────────────────────────────────

    def _start(self):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        self._context = self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="de-AT",
            timezone_id="Europe/Vienna",
            java_script_enabled=True,
        )
        self._page = self._context.new_page()
        self._page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['de-AT','de','en'] });
            window.chrome = { runtime: {} };
        """)

    def _stop(self):
        for obj in [self._page, self._context, self._browser, self._playwright]:
            try:
                if obj:
                    (obj.stop if hasattr(obj, "stop") else obj.close)()
            except Exception:
                pass

    # ── Session warm-up + API discovery ──────────────────────────────────────

    def _establish_session(self) -> bool:
        """
        Navigate to SPAR and discover the search API URL.

        Strategy:
        1. Load homepage to clear Cloudflare
        2. Load search page and wait for the API response (up to 20s)
        3. If interception missed it, fire the API call directly via browser fetch
           using the known URL template
        """
        print("[*] Establishing browser session with SPAR…")
        discovered = {}

        def _on_response(resp):
            try:
                if self.API_HOST in resp.url and "search" in resp.url and resp.status == 200:
                    data = resp.json()
                    if data.get("hits") and "paging" in data:
                        discovered["url"] = resp.url
                        discovered["data"] = data
            except Exception:
                pass

        self._page.on("response", _on_response)

        # Step 1: homepage (establishes Cloudflare cookies)
        try:
            self._page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=30_000)
            self._page.wait_for_timeout(2_000)
        except Exception as e:
            print(f"[!] Homepage navigation error: {e}")

        # Step 2: search page — use domcontentloaded to avoid networkidle timeout
        for attempt in range(1, 4):
            try:
                self._page.goto(
                    f"{self.SEARCH_URL}?search=&page=1",
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )
                # Wait for the Vue/Nuxt app to fire the API call (up to 15s)
                for _ in range(30):
                    self._page.wait_for_timeout(500)
                    if "url" in discovered:
                        break
            except Exception as e:
                print(f"[!] Search page navigation error (attempt {attempt}): {e}")

            if "url" in discovered:
                break

            print(f"[*] API not intercepted yet (attempt {attempt}), waiting longer…")
            self._page.wait_for_timeout(3_000)

        # Step 3: if still not found, fire a known URL directly from the browser
        if "url" not in discovered:
            print("[*] Interception missed — firing API call directly via browser fetch…")
            known_url = (
                f"https://{self.API_HOST}/ecom/pw/v1/search/v1/search"
                "?query=*&sort=Relevancy:asc&page=1&marketId=NATIONAL&hitsPerPage=32"
            )
            try:
                result = self._page.evaluate(
                    """async (url) => {
                        const r = await fetch(url, {headers: {Accept: 'application/json'}});
                        return r.ok ? await r.json() : null;
                    }""",
                    known_url,
                )
                if result and result.get("hits") and "paging" in result:
                    discovered["url"]  = known_url
                    discovered["data"] = result
                    print("[✓] Got API response via direct fetch")
            except Exception as e:
                print(f"[!] Direct fetch also failed: {e}")

        if "url" not in discovered:
            print("[!] Could not discover SPAR API endpoint. Aborting.")
            return False

        raw_url = discovered["url"]
        self._api_url = re.sub(r"([?&]page=)\d+", r"\g<1>{page}", raw_url)
        paging = discovered["data"].get("paging", {})
        total  = discovered["data"].get("totalHits", 0)

        print(f"[✓] API discovered: {self._api_url[:100]}")
        print(f"[*] Total products: {total} across {paging.get('pageCount', '?')} pages")
        return True

    def _reset_context(self):
        """
        Close the current browser context and open a fresh one with full CF warm-up.
        Cloudflare rate-limits per context (~70 requests), so cycling contexts
        resets the counter. We fully warm up (homepage + search page) before returning
        so the next _fetch_page call goes to a ready session.
        """
        try:
            self._page.close()
        except Exception:
            pass
        try:
            self._context.close()
        except Exception:
            pass

        self._context = self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="de-AT",
            timezone_id="Europe/Vienna",
            java_script_enabled=True,
        )
        self._page = self._context.new_page()
        self._page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['de-AT','de','en'] });
            window.chrome = { runtime: {} };
        """)
        # Step 1: homepage — establish base CF cookies
        try:
            self._page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=25_000)
            self._page.wait_for_timeout(2_000)
        except Exception as e:
            print(f"[!] Context reset homepage error: {e}")

        # Step 2: search page — trigger the API XHR so CF validates the session fully
        confirmed = {}

        def _on_warm(resp):
            try:
                if self.API_HOST in resp.url and "search" in resp.url and resp.status == 200:
                    data = resp.json()
                    if data.get("hits"):
                        confirmed["ok"] = True
            except Exception:
                pass

        self._page.on("response", _on_warm)
        try:
            self._page.goto(
                f"{self.SEARCH_URL}?search=&page=1",
                wait_until="domcontentloaded",
                timeout=25_000,
            )
            for _ in range(20):
                self._page.wait_for_timeout(500)
                if confirmed.get("ok"):
                    break
        except Exception as e:
            print(f"[!] Context reset search page error: {e}")
        finally:
            self._page.remove_listener("response", _on_warm)

        if not confirmed.get("ok"):
            print("[!] CF warm-up did not confirm API — waiting 90s for IP block to expire…")
            time.sleep(90)
            # One more attempt after the wait
            confirmed2 = {}
            def _on_retry(resp):
                try:
                    if self.API_HOST in resp.url and "search" in resp.url and resp.status == 200:
                        data = resp.json()
                        if data.get("hits"):
                            confirmed2["ok"] = True
                except Exception:
                    pass
            self._page.on("response", _on_retry)
            try:
                self._page.goto(
                    f"{self.SEARCH_URL}?search=&page=1",
                    wait_until="domcontentloaded",
                    timeout=25_000,
                )
                for _ in range(20):
                    self._page.wait_for_timeout(500)
                    if confirmed2.get("ok"):
                        break
            except Exception:
                pass
            finally:
                self._page.remove_listener("response", _on_retry)
            if not confirmed2.get("ok"):
                print("[!] Still blocked after wait — will try anyway")

    def _hard_refresh_session(self) -> bool:
        """
        Re-establish the Cloudflare session.
        Step 1: navigate to the homepage (resets CF cookie TTL).
        Step 2: navigate to the search page and wait for a real API response.
        Returns True when the session is confirmed working.
        """
        confirmed = {}

        def _on_resp(resp):
            try:
                if self.API_HOST in resp.url and "search" in resp.url and resp.status == 200:
                    data = resp.json()
                    if data.get("hits"):
                        confirmed["ok"] = True
            except Exception:
                pass

        self._page.on("response", _on_resp)
        try:
            # Step 1: homepage re-establishes Cloudflare trust
            self._page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=25_000)
            self._page.wait_for_timeout(2_000)

            # Step 2: search page — triggers the XHR we intercept
            self._page.goto(
                f"{self.SEARCH_URL}?search=&page=1",
                wait_until="domcontentloaded",
                timeout=25_000,
            )
            # Poll up to 15 seconds for a real API response
            for _ in range(30):
                self._page.wait_for_timeout(500)
                if confirmed.get("ok"):
                    break
        except Exception as e:
            print(f"[!] Hard refresh navigation error: {e}")
        finally:
            self._page.remove_listener("response", _on_resp)

        if confirmed.get("ok"):
            print("[✓] Session confirmed\n")
            return True

        # Last resort: try a direct fetch with current cookies
        try:
            known = (
                f"https://{self.API_HOST}/ecom/pw/v1/search/v1/search"
                "?query=*&sort=Relevancy:asc&page=1&marketId=NATIONAL&hitsPerPage=32"
            )
            result = self._page.evaluate(
                "async (u) => { const r = await fetch(u, "
                "{headers:{Accept:'application/json'}}); return r.ok ? 'ok' : r.status; }",
                known,
            )
            if result == "ok":
                print("[✓] Session confirmed via direct fetch\n")
                return True
        except Exception:
            pass

        print("[!] Session refresh failed\n")
        return False

    # ── Per-page fetch (via real browser navigation + XHR interception) ──────────

    def _fetch_page(self, page_num: int) -> Optional[Dict]:
        """
        Navigate the browser to the SPAR search page for page_num and intercept
        the API XHR response. This avoids Cloudflare's programmatic-fetch rate limit
        (which triggers after ~70 calls) because real navigation is not rate-limited.
        """
        captured: Dict = {}

        def _on_resp(resp):
            try:
                if (self.API_HOST in resp.url
                        and "search" in resp.url
                        and f"page={page_num}" in resp.url
                        and resp.status == 200
                        and not captured.get("data")):
                    data = resp.json()
                    if data.get("hits"):
                        captured["data"] = data
            except Exception:
                pass

        self._page.on("response", _on_resp)
        try:
            self._page.goto(
                f"{self.SEARCH_URL}?search=&page={page_num}",
                wait_until="domcontentloaded",
                timeout=25_000,
            )
            # Poll up to 10s for the API XHR to fire
            for _ in range(20):
                self._page.wait_for_timeout(500)
                if captured.get("data"):
                    break
        except Exception as e:
            print(f"[!] Navigation error on page {page_num}: {e}")
            return None
        finally:
            self._page.remove_listener("response", _on_resp)

        return captured.get("data")

    # ── Product normalization ─────────────────────────────────────────────────

    def _normalize_hit(self, hit: Dict) -> Optional[Dict]:
        """Convert a raw API hit into our standard product dict."""
        mv = hit.get("masterValues", {})

        name1 = (mv.get("name1") or "").strip()   # brand
        name2 = (mv.get("name2") or "").strip()   # product name
        name3 = (mv.get("name3") or "").strip()   # size/quantity

        # Build the full product name; name1 is often the brand prefix
        full_name = " ".join(p for p in [name1, name2] if p).strip()
        if not full_name:
            return None

        # Price data
        geo_list = mv.get("geoInformation", [])
        if not geo_list:
            return None
        gv = geo_list[0].get("geoValues", {})

        calculated_price = gv.get("calculatedPrice")
        base_price = gv.get("basePrice")
        statt_price = gv.get("stattPrice")

        if calculated_price is None:
            return None
        if float(calculated_price) <= 0:
            return None

        # Per-unit price (Grundpreis — legally required in Austria)
        comparison_price = gv.get("comparisonPrice_price")
        comparison_qty   = gv.get("comparisonPrice_quantity") or 1
        comparison_unit  = gv.get("comparisonPrice_unit") or None

        # Extra product-tier flags
        is_preis_gesenkt = bool(gv.get("isPreisGesenkt"))   # permanent reduction
        immer_billig     = bool(gv.get("immerBillig"))       # SPAR budget tier
        menge_rabatt     = bool(gv.get("mengenRabatt"))      # quantity discount
        has_app_voucher  = bool(gv.get("hasAppVoucher"))     # app-only deal

        # Promotion detection
        in_angebot = bool(gv.get("inAngebot") or gv.get("hasAktionsPrice"))
        promo_text = gv.get("promotionBadgeText") or None

        # Detect deal type from badge text (before price logic, used in DB write)
        # Patterns: "1+1 GRATIS", "2+1 GRATIS", "3+1 GRATIS", "BOGO", etc.
        deal_type = "percentage"  # default
        quantity_trigger = None   # buy X
        quantity_free = None      # get Y free
        if promo_text:
            m = re.match(r"(\d+)\+(\d+)\s*(?:gratis|free)", promo_text, re.IGNORECASE)
            if m:
                quantity_trigger = int(m.group(1))
                quantity_free = int(m.group(2))
                deal_type = "bogo"

        # When on promotion:
        #   calculatedPrice = promo price
        #   basePrice OR stattPrice = shelf price
        if in_angebot:
            current_price = float(calculated_price)
            original_price = float(statt_price or base_price or calculated_price)
            if original_price <= current_price:
                # Fallback: not actually cheaper
                original_price = None
                in_angebot = False
        else:
            current_price = float(base_price or calculated_price)
            original_price = None

        discount_pct = None
        if in_angebot and original_price and deal_type == "percentage":
            discount_pct = round((original_price - current_price) / original_price * 100, 1)

        # Try to extract end date from badge text (e.g. "noch bis 14.06." or "bis 31.12.2024")
        offer_end_date = _parse_date_de(promo_text) if promo_text else None

        # Image
        image_url = _image_url(mv.get("productImage_assetUrl", ""))

        # Product URL
        slug = mv.get("slug", "")
        product_url = f"{self.BASE_URL}/produktwelt/{slug}" if slug else None

        # Unit info from name3 (size field)
        unit, size_normalized = _extract_unit(name3 or full_name)

        # Compute per-unit price: prefer API Grundpreis, fall back to calculation
        unit_price = None
        unit_price_unit = comparison_unit
        if comparison_price and float(comparison_price) > 0:
            unit_price = round(float(comparison_price) / float(comparison_qty), 4)
        elif size_normalized and size_normalized > 0 and current_price:
            unit_price = round(current_price / size_normalized, 4)
            unit_price_unit = unit

        return {
            "name": full_name,
            "brand": name1 or None,
            "price": current_price,
            "original_price": original_price if in_angebot else None,
            "is_promotion": in_angebot,
            "discount_percentage": discount_pct,
            "deal_type": deal_type,
            "quantity_trigger": quantity_trigger,
            "quantity_free": quantity_free,
            "promo_text": promo_text,
            "offer_end_date": offer_end_date,
            "is_preis_gesenkt": is_preis_gesenkt,
            "immer_billig": immer_billig,
            "menge_rabatt": menge_rabatt,
            "has_app_voucher": has_app_voucher,
            "unit_price": unit_price,
            "unit_price_unit": unit_price_unit,
            "image_url": image_url,
            "product_url": product_url,
            "unit": unit,
            "size_normalized": size_normalized,
            "scraped_at": datetime.now(timezone.utc),
        }

    # ── Main scrape loop ──────────────────────────────────────────────────────

    def scrape_all(self, max_pages: Optional[int] = None, delay: float = 0.3) -> List[Dict]:
        """
        Scrape all SPAR products. Returns a deduplicated list of product dicts.
        Uses in-browser fetch for each page — no page navigation, much faster.
        """
        print(f"\n{'='*70}")
        print("SPAR DIRECT SCRAPER — Starting")
        print(f"{'='*70}\n")

        self._start()
        all_products: List[Dict] = []
        seen_fps: set = set()

        try:
            if not self._establish_session():
                return []

            # Get total pages from first API call (already captured)
            first_page_data = self._fetch_page(1)
            if not first_page_data:
                print("[!] Could not fetch page 1")
                return []

            paging = first_page_data.get("paging", {})
            total_pages = paging.get("pageCount", 1200)
            total_products = first_page_data.get("totalHits", 0)

            if max_pages:
                total_pages = min(total_pages, max_pages)

            print(f"[*] Scraping {total_pages} pages (~{total_products} products)\n")

            consecutive_errors = 0
            no_new_streak = 0
            CONTEXT_RESET_EVERY = 30  # reset browser context every N pages

            for page_num in range(1, total_pages + 1):
                # Page 1 data was already fetched above
                if page_num == 1:
                    page_data = first_page_data
                else:
                    # Proactively reset context before CF rate-limit kicks in
                    if page_num % CONTEXT_RESET_EVERY == 0:
                        print(f"\n[*] Resetting browser context at page {page_num}…")
                        self._reset_context()
                        print("[✓] Fresh context ready\n")

                    page_data = self._fetch_page(page_num)

                if not page_data:
                    consecutive_errors += 1
                    print(f"[!] No data on page {page_num} — waiting 120s for CF to unblock…")
                    # CF IP blocks are time-windowed; wait before resetting
                    time.sleep(120)
                    self._reset_context()
                    page_data = self._fetch_page(page_num)
                    if page_data:
                        consecutive_errors = 0
                        print("[✓] Recovered\n")

                    if not page_data:
                        if consecutive_errors >= 5:
                            print("[!] 5 unrecoverable errors — stopping.")
                            break
                        print(f"[!] Skipping page {page_num} after recovery attempt")
                        continue

                consecutive_errors = 0
                hits = page_data.get("hits", [])
                self.stats["pages_fetched"] += 1

                new_count = 0
                for hit in hits:
                    try:
                        product = self._normalize_hit(hit)
                        if not product:
                            continue
                        fp = _fingerprint(
                            product["name"],
                            product.get("brand", ""),
                            product.get("unit", ""),
                            product.get("size_normalized"),
                        )
                        if fp not in seen_fps:
                            seen_fps.add(fp)
                            all_products.append(product)
                            new_count += 1
                            self.stats["products_extracted"] += 1
                    except Exception as e:
                        self.stats["errors"] += 1

                print(
                    f"[✓] Page {page_num}/{total_pages} | "
                    f"+{new_count} new | Total: {len(all_products)}"
                )

                if new_count == 0:
                    no_new_streak += 1
                    if no_new_streak >= 30:
                        print("[*] 30 pages with no new products — end of unique catalog.")
                        break
                else:
                    no_new_streak = 0

                if page_num % 100 == 0:
                    print(f"\n[*] Checkpoint: {len(all_products)} unique products after {page_num} pages\n")

                if delay > 0:
                    time.sleep(delay)

        except KeyboardInterrupt:
            print(f"\n[!] Interrupted. Collected {len(all_products)} products so far.")
        finally:
            self._stop()

        print(f"\n{'='*70}")
        print(f"[✓] Scrape complete: {len(all_products)} unique products, {self.stats['pages_fetched']} pages")
        print(f"{'='*70}\n")
        return all_products

    # ── Database save ─────────────────────────────────────────────────────────

    def save_to_database(self, products: List[Dict], db_session) -> Dict:
        """
        Upsert scraped products into PostgreSQL using bulk SQL.

        Performance strategy:
        - Phase 1: bulk INSERT products ON CONFLICT DO UPDATE RETURNING id, fingerprint
          → one SQL for all products, gets back all IDs in one round-trip
        - Phase 2: bulk INSERT product_store ON CONFLICT DO UPDATE
          → one SQL for all store rows
        - Phase 3: bulk INSERT price_history for changed prices only
        - Phase 4: ORM loop for promotions (small subset, ~5% of products)
        - Phase 5: bulk UPDATE last_seen + mark unseen unavailable
        Total: ~8 SQL statements regardless of product count.
        """
        from sqlalchemy import text as _text
        from models.postgres_models import (
            Store, Promotion, Offer, PromotionTarget, PriceHistory,
        )

        print(f"\n{'='*70}")
        print(f"DATABASE — Upserting {len(products)} products")
        print(f"{'='*70}\n")

        # ── Ensure SPAR store row exists ──────────────────────────────────────
        store = db_session.execute(
            _text("SELECT store_id FROM stores WHERE store_id = :sid"),
            {"sid": self.STORE_ID},
        ).first()
        if not store:
            db_session.execute(_text("""
                INSERT INTO stores (store_id, name, website, logo_url, country,
                                    api_available, scraping_required, active)
                VALUES (:sid, 'SPAR', 'https://www.spar.at',
                        'https://www.spar.at/favicon.ico', 'AT',
                        false, true, true)
                ON CONFLICT (store_id) DO NOTHING
            """), {"sid": self.STORE_ID})
            db_session.commit()
            print("[✓] SPAR store row created")

        now = datetime.now(timezone.utc)
        stats = {
            "processed": 0, "products_added": 0, "products_updated": 0,
            "ps_added": 0, "ps_updated": 0, "price_changes_recorded": 0,
            "promotions_added": 0, "promotions_updated": 0,
            "promotions_deactivated": 0, "validation_errors": 0, "db_errors": 0,
        }

        # ── Validate and prepare product rows ────────────────────────────────
        print("[*] Preparing product rows…")
        valid: List[Dict] = []
        for data in products:
            name = (data.get("name") or "").strip()
            price = data.get("price")
            if not name or price is None or float(price) <= 0:
                stats["validation_errors"] += 1
                continue
            original_price = data.get("original_price")
            if original_price and float(original_price) < float(price):
                original_price, price = price, original_price
            fp = _fingerprint(
                name, data.get("brand", ""), data.get("unit", ""),
                data.get("size_normalized"),
            )
            valid.append({**data, "_fp": fp, "_price": price,
                          "_original_price": original_price})
        stats["processed"] = len(products)
        print(f"[*] {len(valid)} valid products to upsert\n")

        # ── Phase 1: bulk upsert products, get back fingerprint → id map ────
        print("[*] Phase 1: upserting products table…")
        fp_to_id: dict = {}
        CHUNK = 500
        for i in range(0, len(valid), CHUNK):
            chunk = valid[i:i + CHUNK]
            rows = [
                {
                    "fp": d["_fp"], "name": d.get("name"), "brand": d.get("brand"),
                    "unit": d.get("unit"), "size": _safe_decimal(d.get("size_normalized")),
                    "img": d.get("image_url"), "now": now,
                }
                for d in chunk
            ]
            # Build VALUES list for this chunk
            placeholders = ", ".join(
                f"(:fp{j}, :name{j}, :name{j}, :brand{j}, :unit{j}, :size{j}, :img{j}, :now{j}, :now{j})"
                for j in range(len(rows))
            )
            params = {}
            for j, r in enumerate(rows):
                params.update({
                    f"fp{j}": r["fp"], f"name{j}": r["name"],
                    f"brand{j}": r["brand"], f"unit{j}": r["unit"],
                    f"size{j}": r["size"], f"img{j}": r["img"],
                    f"now{j}": r["now"],
                })
            result = db_session.execute(_text(f"""
                INSERT INTO products
                    (fingerprint, name, name_de, brand, unit_normalized,
                     size_normalized, default_image_url, created_at, updated_at)
                VALUES {placeholders}
                ON CONFLICT (fingerprint) DO UPDATE SET
                    brand             = COALESCE(products.brand, EXCLUDED.brand),
                    default_image_url = COALESCE(products.default_image_url,
                                                 EXCLUDED.default_image_url),
                    updated_at        = CASE
                        WHEN products.brand IS NULL AND EXCLUDED.brand IS NOT NULL
                          OR products.default_image_url IS NULL
                             AND EXCLUDED.default_image_url IS NOT NULL
                        THEN EXCLUDED.updated_at
                        ELSE products.updated_at
                    END
                RETURNING id, fingerprint
            """), params)
            for row in result:
                fp_to_id[row.fingerprint] = row.id
            print(f"    products upserted: {min(i + CHUNK, len(valid))}/{len(valid)}")

        db_session.commit()
        print(f"[✓] Phase 1 done — {len(fp_to_id)} product IDs\n")

        # ── Phase 2: load old product_store prices (for price-change detection) ──
        print("[*] Phase 2: loading existing product_store prices…")
        old_prices: dict = {}  # product_id → Decimal
        for row in db_session.execute(_text(
            "SELECT product_id, base_price FROM product_store WHERE store_id = :sid"
        ), {"sid": self.STORE_ID}):
            old_prices[row.product_id] = row.base_price

        # ── Phase 3: bulk upsert product_store ──────────────────────────────
        print("[*] Phase 3: upserting product_store…")
        seen_product_ids: set = set()
        price_history_rows: list = []

        for i in range(0, len(valid), CHUNK):
            chunk = valid[i:i + CHUNK]
            ps_rows = []
            for d in chunk:
                pid = fp_to_id.get(d["_fp"])
                if not pid:
                    continue
                seen_product_ids.add(pid)
                is_promo = bool(d.get("is_promotion") and d["_original_price"])
                shelf_price = _safe_decimal(d["_original_price"] if is_promo else d["_price"])
                old_price = old_prices.get(pid)
                if old_price is not None and old_price != shelf_price:
                    price_history_rows.append({
                        "pid": pid, "sid": self.STORE_ID,
                        "old": old_price, "new": shelf_price, "now": now,
                    })
                    stats["price_changes_recorded"] += 1
                ps_rows.append({
                    "pid": pid, "sid": self.STORE_ID,
                    "price": shelf_price,
                    "url": d.get("product_url"),
                    "now": now,
                    "unit_price": _safe_decimal(d.get("unit_price")),
                    "unit_unit": d.get("unit_price_unit"),
                    "is_pg": bool(d.get("is_preis_gesenkt")),
                    "is_ib": bool(d.get("immer_billig")),
                    "is_av": bool(d.get("has_app_voucher")),
                })

            if not ps_rows:
                continue

            placeholders = ", ".join(
                f"(:pid{j}, :sid{j}, :price{j}, true, :url{j}, :now{j}, :now{j},"
                f" :unit_price{j}, :unit_unit{j}, :is_pg{j}, :is_ib{j}, :is_av{j})"
                for j in range(len(ps_rows))
            )
            params = {}
            for j, r in enumerate(ps_rows):
                params.update({
                    f"pid{j}": r["pid"], f"sid{j}": r["sid"],
                    f"price{j}": r["price"], f"url{j}": r["url"],
                    f"now{j}": r["now"],
                    f"unit_price{j}": r["unit_price"],
                    f"unit_unit{j}": r["unit_unit"],
                    f"is_pg{j}": r["is_pg"], f"is_ib{j}": r["is_ib"],
                    f"is_av{j}": r["is_av"],
                })
            db_session.execute(_text(f"""
                INSERT INTO product_store
                    (product_id, store_id, base_price, is_available, product_url,
                     last_seen, created_at,
                     unit_price, unit_price_unit,
                     is_preis_gesenkt, immer_billig, has_app_voucher)
                VALUES {placeholders}
                ON CONFLICT (product_id, store_id) DO UPDATE SET
                    base_price        = EXCLUDED.base_price,
                    is_available      = true,
                    product_url       = COALESCE(EXCLUDED.product_url,
                                                 product_store.product_url),
                    last_seen         = EXCLUDED.last_seen,
                    unit_price        = EXCLUDED.unit_price,
                    unit_price_unit   = EXCLUDED.unit_price_unit,
                    is_preis_gesenkt  = EXCLUDED.is_preis_gesenkt,
                    immer_billig      = EXCLUDED.immer_billig,
                    has_app_voucher   = EXCLUDED.has_app_voucher
            """), params)
            stats["ps_updated"] += len(ps_rows)

        db_session.commit()
        print(f"[✓] Phase 3 done — {stats['ps_updated']} rows, "
              f"{stats['price_changes_recorded']} price changes\n")

        # ── Phase 4: bulk insert price history ───────────────────────────────
        if price_history_rows:
            print(f"[*] Phase 4: inserting {len(price_history_rows)} price history rows…")
            for i in range(0, len(price_history_rows), CHUNK):
                chunk = price_history_rows[i:i + CHUNK]
                placeholders = ", ".join(
                    f"(:pid{j}, :sid{j}, :old{j}, :new{j}, :now{j}, :now{j}, :new{j})"
                    for j in range(len(chunk))
                )
                params = {}
                for j, r in enumerate(chunk):
                    params.update({
                        f"pid{j}": r["pid"], f"sid{j}": r["sid"],
                        f"old{j}": r["old"], f"new{j}": r["new"], f"now{j}": r["now"],
                    })
                db_session.execute(_text(f"""
                    INSERT INTO price_history
                        (product_id, store_id, old_price, new_price,
                         changed_at, recorded_at, price)
                    VALUES {placeholders}
                """), params)
            db_session.commit()
            print(f"[✓] Phase 4 done\n")

        # ── Phase 5: promotions (ORM, only promo products) ──────────────────
        print("[*] Phase 5: handling promotions…")
        promo_products = [d for d in valid if d.get("is_promotion") and d["_original_price"]]

        if promo_products:
            # Load active promo targets for affected product IDs
            promo_pids = [fp_to_id[d["_fp"]] for d in promo_products if d["_fp"] in fp_to_id]
            active_promo_targets: dict = {}
            active_offers: dict = {}
            promo_by_id: dict = {}

            if promo_pids:
                targets = (
                    db_session.query(PromotionTarget)
                    .filter(
                        PromotionTarget.store_id == self.STORE_ID,
                        PromotionTarget.product_id.in_(promo_pids),
                    )
                    .all()
                )
                promo_ids = list({t.promotion_id for t in targets})
                if promo_ids:
                    for p in db_session.query(Promotion).filter(
                        Promotion.id.in_(promo_ids), Promotion.is_active == True
                    ).all():
                        promo_by_id[p.id] = p
                    offer_ids = [p.offer_id for p in promo_by_id.values() if p.offer_id]
                    if offer_ids:
                        for o in db_session.query(Offer).filter(
                            Offer.id.in_(offer_ids)
                        ).all():
                            active_offers[o.id] = o
                # Store target → promotion_id mapping without touching ORM relationships
                for t in targets:
                    promo = promo_by_id.get(t.promotion_id)
                    if promo and promo.is_active:
                        active_promo_targets.setdefault(t.product_id, []).append(t.promotion_id)

            for d in promo_products:
                pid = fp_to_id.get(d["_fp"])
                if not pid:
                    continue
                name = d.get("name", "")
                price = d["_price"]
                original_price = d["_original_price"]
                discount_val = d.get("discount_percentage") or round(
                    (float(original_price) - float(price)) / float(original_price) * 100, 1
                )
                end_date_obj = d.get("offer_end_date")
                end_date = end_date_obj.date() if end_date_obj else None
                deal_type = d.get("deal_type", "percentage")
                qty_trigger = d.get("quantity_trigger")
                qty_free = d.get("quantity_free")
                if deal_type == "bogo" and qty_trigger and qty_free:
                    effective_pct = round(qty_free / (qty_trigger + qty_free) * 100, 1)
                    offer_discount_val = _safe_decimal(effective_pct)
                    offer_min_qty = qty_trigger
                else:
                    offer_discount_val = _safe_decimal(discount_val)
                    offer_min_qty = 1
                offer_label = (d.get("promo_text") or f"SPAR {discount_val}% Rabatt")[:100]

                active_promo_ids = active_promo_targets.get(pid, [])
                if active_promo_ids:
                    promo = promo_by_id.get(active_promo_ids[0])
                    if promo:
                        linked_offer = active_offers.get(promo.offer_id) if promo.offer_id else None
                        if linked_offer:
                            linked_offer.name = offer_label
                            linked_offer.discount_type = deal_type
                            linked_offer.discount_value = offer_discount_val or _safe_decimal(0)
                            linked_offer.min_quantity = offer_min_qty
                            linked_offer.description = d.get("promo_text") or ""
                            linked_offer.is_active = True
                            linked_offer.updated_at = now
                        promo.name = f"SPAR Aktion — {name[:50]}"
                        promo.description = d.get("promo_text") or ""
                        if end_date:
                            promo.end_date = end_date
                        promo.is_active = True
                        stats["promotions_updated"] += 1
                else:
                    offer = Offer(
                        name=offer_label,
                        description=d.get("promo_text") or "",
                        discount_type=deal_type,
                        discount_value=offer_discount_val or _safe_decimal(0),
                        min_quantity=offer_min_qty,
                        is_active=True, created_at=now, updated_at=now,
                    )
                    db_session.add(offer)
                    db_session.flush()
                    promo = Promotion(
                        name=f"SPAR Aktion — {name[:50]}",
                        description=d.get("promo_text") or "",
                        offer_id=offer.id,
                        start_date=now.date(), end_date=end_date,
                        is_active=True, created_at=now,
                    )
                    db_session.add(promo)
                    db_session.flush()
                    db_session.add(PromotionTarget(
                        promotion_id=promo.id, product_id=pid,
                        store_id=self.STORE_ID, created_at=now,
                    ))
                    stats["promotions_added"] += 1

            db_session.commit()

        # Deactivate promotions for products seen this run that are no longer on promo.
        # NOTE: active_promo_targets is only loaded for current-promo products, so we
        # do a direct SQL query for all seen non-promo products with active promotions.
        promo_pids_set = {fp_to_id[d["_fp"]] for d in promo_products if d["_fp"] in fp_to_id}
        non_promo_seen = list(set(seen_product_ids) - promo_pids_set)
        if non_promo_seen:
            deact_result = db_session.execute(_text("""
                UPDATE promotions SET is_active = false,
                    end_date = COALESCE(end_date, CURRENT_DATE)
                WHERE is_active = true
                  AND id IN (
                      SELECT pt.promotion_id FROM promotion_targets pt
                      WHERE pt.store_id = :sid
                        AND pt.product_id = ANY(:pids)
                  )
                RETURNING id, offer_id
            """), {"sid": self.STORE_ID, "pids": non_promo_seen})
            deact_rows = deact_result.fetchall()
            if deact_rows:
                stats["promotions_deactivated"] += len(deact_rows)
                offer_ids_to_deact = [r.offer_id for r in deact_rows if r.offer_id]
                if offer_ids_to_deact:
                    db_session.execute(_text(
                        "UPDATE offers SET is_active = false, updated_at = :now "
                        "WHERE id = ANY(:ids)"
                    ), {"now": now, "ids": offer_ids_to_deact})
                db_session.commit()

        print(f"[✓] Phase 5 done — {stats['promotions_added']} added, "
              f"{stats['promotions_updated']} updated, "
              f"{stats['promotions_deactivated']} deactivated\n")

        # ── Phase 6: mark unseen products unavailable ────────────────────────
        print("[*] Phase 6: marking unseen products unavailable…")
        if seen_product_ids:
            db_session.execute(
                _text(
                    "UPDATE product_store SET is_available = false "
                    "WHERE store_id = :sid AND product_id NOT IN :ids "
                    "AND is_available = true"
                ),
                {"sid": self.STORE_ID, "ids": tuple(seen_product_ids)},
            )
            stale_count = db_session.execute(
                _text(
                    "SELECT COUNT(*) FROM product_store "
                    "WHERE store_id = :sid AND is_available = false "
                    "AND product_id NOT IN :ids"
                ),
                {"sid": self.STORE_ID, "ids": tuple(seen_product_ids)},
            ).scalar()
            db_session.commit()
            print(f"[✓] Phase 6 done — {stale_count} products marked unavailable\n")

        self.stats["products_added"] = stats["products_added"]
        self.stats["promotions_added"] = stats["promotions_added"]

        print(f"\n{'='*70}")
        print("DATABASE COMPLETE")
        for k, v in stats.items():
            print(f"  {k:<35} {v}")
        print(f"{'='*70}\n")
        return stats


# ─────────────────────────────────────────────────────────────────────────────
# Entry point (called from run_spar_direct.py)
# ─────────────────────────────────────────────────────────────────────────────

def main(max_pages: Optional[int] = None, headless: bool = True):
    from app import app
    from models.postgres_models import db

    with app.app_context():
        scraper = SparDirectScraper(headless=headless)
        products = scraper.scrape_all(max_pages=max_pages, delay=0.3)
        if products:
            scraper.save_to_database(products, db.session)
        else:
            print("[!] No products scraped.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--visible", action="store_true")
    args = parser.parse_args()
    main(max_pages=args.max_pages, headless=not args.visible)
