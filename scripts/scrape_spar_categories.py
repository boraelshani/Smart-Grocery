"""
SPAR Category Assignment
========================
1. Walks SPAR's category tree via their breadcrumb API (browser fetch to bypass CF)
2. Creates matching rows in our `categories` table if they don't exist
3. For each leaf category, queries the SPAR search API with pwCategoryPathIDs filter
4. Assigns category_id to every matching product in our DB

Run:
    ./venv/bin/python3 scripts/scrape_spar_categories.py
    ./venv/bin/python3 scripts/scrape_spar_categories.py --dry-run   # no DB writes
"""
import sys, os, time, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from app import app
from models.postgres_models import db, Product, ProductStore, Category

STORE_ID   = "spar"
API_HOST   = "api-scp.spar-ics.com"
TOP_CATS   = ["lebensmittel", "getraenke", "drogerie-beauty", "haushalt"]

# Maps SPAR category slugs we can't translate automatically
TITLE_OVERRIDES = {
    "drogerie-beauty": "Drogerie & Beauty",
    "haushalt": "Haushalt",
}


# ── Browser helpers ────────────────────────────────────────────────────────────

def _rewarm_session(page):
    """Navigate back to spar.at to refresh CF session after API browsing."""
    try:
        page.goto("https://www.spar.at", wait_until="domcontentloaded", timeout=20_000)
        page.wait_for_timeout(2_000)
        page.goto("https://www.spar.at/produktwelt/suche?search=&page=1",
                  wait_until="domcontentloaded", timeout=20_000)
        page.wait_for_timeout(3_000)
    except Exception:
        pass


def _browser_fetch(page, url: str) -> dict | None:
    """
    Navigate the browser to the API URL and parse JSON from page body.
    CF allows this because it's real browser navigation (not programmatic fetch).
    """
    import json as _json
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15_000)
        text = page.evaluate("document.body.innerText")
        if not text or not text.strip().startswith(("{", "[")):
            return None  # CF challenge page
        return _json.loads(text)
    except Exception:
        return None


def _fetch_category_node(page, slug: str) -> dict | None:
    """
    Returns the category node for `slug` including its childCategories.
    The breadcrumb API returns the full path; the LAST element is the requested node.
    """
    url = f"https://{API_HOST}/ecom/pw/v1/category/v1/at/breadcrumb/{slug}"
    data = _browser_fetch(page, url)
    if not data or not isinstance(data, list):
        return None
    return data[-1]  # last element = the requested category


def _walk_tree(page, slug: str, level: int = 1) -> list:
    """
    Recursively collect all categories as flat list of dicts:
      {slug, title, level, parent_slug, is_leaf}
    """
    node = _fetch_category_node(page, slug)
    if not node:
        return []

    title    = TITLE_OVERRIDES.get(slug) or node.get("title", slug)
    children = node.get("childCategories") or []
    is_leaf  = len(children) == 0

    result = [{"slug": slug, "title": title, "level": level, "is_leaf": is_leaf}]

    for child in children:
        child_slug = child["categoryId"]
        time.sleep(0.15)
        result += _walk_tree(page, child_slug, level + 1)

    return result


def _search_products_in_category(page, slug: str, api_url_template: str) -> list:
    """
    Fetch all productIds belonging to a SPAR category using the filtered search API.
    Returns a list of SPAR productId strings.
    """
    product_ids = []
    page_num = 1

    while True:
        url = (
            api_url_template
            .replace("{page}", str(page_num))
            + f"&filter=pwCategoryPathIDs%3A{slug}"
        ).replace("/search?", "/navigation?")  # category queries use /navigation

        data = _browser_fetch(page, url)
        if not data or not data.get("hits"):
            break

        for hit in data["hits"]:
            mv = hit.get("masterValues", {})
            pid = mv.get("productId")
            if pid:
                product_ids.append(str(pid))

        paging    = data.get("paging", {})
        total_pgs = paging.get("pageCount", 1)
        if page_num >= total_pgs:
            break
        page_num += 1
        time.sleep(0.2)

    return product_ids


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _get_or_create_category(slug: str, title: str, level: int,
                             parent_id: int | None, dry_run: bool) -> int | None:
    """Return existing or newly-created category id for this slug."""
    cat = db.session.query(Category).filter_by(slug=slug).first()
    if cat:
        # Update name if it was previously stored empty
        if title and (not cat.name_de or not cat.name_en):
            if not dry_run:
                cat.name_de = cat.name_de or title
                cat.name_en = cat.name_en or title
        return cat.id

    if dry_run:
        print(f"      [DRY] Would create category: {slug} — {title} (level {level})")
        return None

    cat = Category(
        slug=slug,
        name_de=title,
        name_en=title,
        level=level,
        parent_id=parent_id,
    )
    db.session.add(cat)
    db.session.flush()
    return cat.id


_spar_url_map: dict = {}  # spar productId str → product_id int (loaded once)

def _ensure_url_map():
    """Load product_url → product_id mapping once for all category assignments."""
    if _spar_url_map:
        return
    import re as _re
    rows = db.session.query(ProductStore.product_url, ProductStore.product_id)\
        .filter(ProductStore.store_id == STORE_ID, ProductStore.product_url.isnot(None)).all()
    for url, pid in rows:
        m = _re.search(r"-p(\d+)$", url or "")
        if m:
            _spar_url_map[m.group(1)] = pid
    print(f"[*] URL map loaded: {len(_spar_url_map)} SPAR products")


_product_cache: dict = {}  # product_id → Product (loaded on demand)

def _assign_category_by_spar_ids(spar_product_ids: list, category_id: int,
                                  dry_run: bool) -> int:
    """
    Match SPAR productIds to our Product rows using the pre-loaded URL map.
    Zero per-product DB queries — all matching is done in memory.
    """
    if not spar_product_ids:
        return 0
    _ensure_url_map()

    product_ids_to_update = []
    for spar_pid in spar_product_ids:
        our_pid = _spar_url_map.get(str(spar_pid))
        if our_pid:
            product_ids_to_update.append(our_pid)

    if not product_ids_to_update or dry_run:
        return len(product_ids_to_update)

    from sqlalchemy import text as _text
    for attempt in range(3):
        try:
            db.session.execute(
                _text(
                    "UPDATE products SET category_id = :cat "
                    "WHERE id = ANY(:ids) AND (category_id IS NULL OR category_id != :cat)"
                ),
                {"cat": category_id, "ids": product_ids_to_update},
            )
            return len(product_ids_to_update)
        except Exception as e:
            print(f"\n      [!] DB error (attempt {attempt+1}): {e} — reconnecting…")
            try:
                db.session.rollback()
                db.session.remove()
            except Exception:
                pass
            time.sleep(3)
    return 0


# ── Main ───────────────────────────────────────────────────────────────────────

def run(dry_run: bool = False):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            locale="de-AT",
            timezone_id="Europe/Vienna",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()

        # Establish Cloudflare session + discover search API URL
        print("[*] Establishing SPAR browser session…")
        api_url_template = None
        import re

        def on_response(resp):
            nonlocal api_url_template
            try:
                if API_HOST in resp.url and "search" in resp.url and resp.status == 200:
                    data = resp.json()
                    if data.get("hits") and not api_url_template:
                        api_url_template = re.sub(r"([?&]page=)\d+", r"\g<1>{page}", resp.url)
            except Exception:
                pass

        page.on("response", on_response)
        page.goto("https://www.spar.at", wait_until="domcontentloaded", timeout=25_000)
        page.wait_for_timeout(2_000)
        page.goto("https://www.spar.at/produktwelt/suche?search=&page=1",
                  wait_until="domcontentloaded", timeout=30_000)
        for _ in range(20):
            page.wait_for_timeout(500)
            if api_url_template:
                break

        if not api_url_template:
            print("[!] Could not detect search API URL. Aborting.")
            browser.close()
            return

        print(f"[✓] API template: {api_url_template[:80]}…\n")

        # Walk the full category tree
        print("[*] Discovering SPAR category tree…")
        all_cats = []
        for top_slug in TOP_CATS:
            print(f"    Walking: {top_slug}")
            cats = _walk_tree(page, top_slug, level=1)
            all_cats.extend(cats)
            # Re-warm between top-level trees — tree walk navigates to API domain
            print(f"      → {len(cats)} categories found, re-warming session…")
            _rewarm_session(page)
            time.sleep(1.0)

        leaf_cats = [c for c in all_cats if c["is_leaf"]]
        print(f"\n[✓] Found {len(all_cats)} categories, {len(leaf_cats)} leaf categories\n")

        with app.app_context():
            # Build slug → category_id map, creating DB rows as we go
            print("[*] Creating/mapping categories in DB…")
            slug_to_id: dict = {}
            slug_to_level: dict = {c["slug"]: c["level"] for c in all_cats}

            # Process in level order so parents exist before children
            for level in range(1, 5):
                for cat in [c for c in all_cats if c["level"] == level]:
                    slug      = cat["slug"]
                    parent_slug = next(
                        (c["slug"] for c in all_cats
                         if c["level"] == level - 1 and slug in [
                             x["slug"] for x in all_cats
                             if x["level"] == level
                         ]),
                        None,
                    )
                    # Better parent lookup: find which top-level tree this slug belongs to
                    # (done via the walk order — parent is the category at level-1 closest before this one)
                    parent_id = None
                    if level > 1:
                        # find parent by going backwards in all_cats
                        idx = next((i for i, c in enumerate(all_cats) if c["slug"] == slug), -1)
                        for j in range(idx - 1, -1, -1):
                            if all_cats[j]["level"] == level - 1:
                                parent_id = slug_to_id.get(all_cats[j]["slug"])
                                break

                    cat_id = _get_or_create_category(
                        slug, cat["title"], level, parent_id, dry_run
                    )
                    if cat_id:
                        slug_to_id[slug] = cat_id

            if not dry_run:
                db.session.commit()
            print(f"[✓] {len(slug_to_id)} categories in DB\n")

            # Re-warm CF session before product search phase (tree walk left us on API domain)
            print("[*] Re-warming CF session before product search…")
            _rewarm_session(page)

            # For each leaf category, fetch products and assign category
            total_assigned = 0
            REWARM_EVERY = 25  # re-navigate to spar.at every N categories
            print("[*] Assigning categories to products…")
            for i, cat in enumerate(leaf_cats):
                slug      = cat["slug"]
                cat_id    = slug_to_id.get(slug)
                if not cat_id and not dry_run:
                    continue

                # Periodically re-warm CF session (navigation to API domain breaks session)
                if i > 0 and i % REWARM_EVERY == 0:
                    print(f"\n[*] Re-warming CF session at category {i}…")
                    _rewarm_session(page)
                    print("[✓] Session refreshed\n")

                print(f"    {slug} (level {cat['level']})…", end=" ", flush=True)
                spar_ids = _search_products_in_category(page, slug, api_url_template)

                # If CF blocked (empty result), retry up to 2x with increasing waits
                if not spar_ids:
                    for cf_attempt in range(2):
                        wait = 60 * (cf_attempt + 1)
                        print(f"[CF block, waiting {wait}s]… ", end="", flush=True)
                        try:
                            _rewarm_session(page)
                            time.sleep(wait)
                            spar_ids = _search_products_in_category(page, slug, api_url_template)
                        except Exception:
                            spar_ids = []
                        if spar_ids:
                            break

                assigned = _assign_category_by_spar_ids(spar_ids, cat_id or 0, dry_run)
                total_assigned += assigned
                print(f"{len(spar_ids)} products found, {assigned} assigned")

                # Commit every 10 categories so progress survives a crash
                if not dry_run and i % 10 == 0:
                    try:
                        db.session.commit()
                    except Exception:
                        db.session.rollback()

                time.sleep(1.0)

            if not dry_run:
                db.session.commit()
                print(f"[✓] Categories committed to DB")

        browser.close()

    print(f"\n{'='*60}")
    print(f"  Total products assigned categories: {total_assigned}")
    print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
