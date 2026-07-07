"""
SPAR Category Assignment
========================
1. Walks SPAR's category tree via their breadcrumb API (browser fetch to bypass CF)
2. For each SPAR leaf category, maps it to one of our existing website category IDs
3. Queries the SPAR search API to find products in that leaf category
4. Updates product.category_id to the mapped website category

Run:
    ./venv/bin/python3 scripts/scrape_spar_categories.py
    ./venv/bin/python3 scripts/scrape_spar_categories.py --dry-run   # no DB writes
"""
import sys, os, time, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from app import app
from models.postgres_models import db, Product, ProductStore

STORE_ID = "spar"
API_HOST = "api-scp.spar-ics.com"
TOP_CATS = ["lebensmittel", "getraenke", "drogerie-beauty", "haushalt"]

# Maps SPAR category slugs → our website category slugs
# Only leaf-level (or close to leaf) SPAR slugs are needed here.
# Any SPAR slug not in this map will be skipped (product stays uncategorized).
SPAR_TO_OUR_SLUG = {
    # ── Obst & Gemüse ──────────────────────────────────────────────────────
    "obst":                             "fruits",
    "beeren":                           "berries",
    "zitrusfruechte":                   "citrus",
    "melonen":                          "melons",
    "steinobst":                        "stone-fruits",
    "exotische-fruechte":               "tropical-fruits",
    "aepfel-birnen-sonstiges-kernobst": "apples-pears",
    "trauben-bananen":                  "grapes-bananas",
    "gemuese":                          "vegetables",
    "blattsalat-blaettergemuese":       "leafy-greens",
    "wurzelgemuese":                    "root-vegetables",
    "kuerbis-paprika":                  "squash-peppers",
    "zwiebeln-knoblauch":               "onions-garlic",
    "pilze":                            "mushrooms",
    "kraeuter":                         "herbs",
    "schnittkreaeuter":                 "cut-herbs",
    "topfkraeuter":                     "potted-herbs",
    "kresse-sprossenbeet":              "cress-sprouts",
    "frischobst-gemuese-vorbereitet":   "prepared-produce",
    "frischgemuese-vorbereitet":        "cut-vegetables",
    "frischobst-vorbereitet":           "cut-fruits",
    "salate-vorbereitet":               "salad-kits",

    # ── Brot & Gebäck ──────────────────────────────────────────────────────
    "brot":                             "fresh-bread",
    "weissbrot":                        "white-bread",
    "vollkornbrot":                     "wheat-bread",
    "sauerteigbrot":                    "sourdough",
    "roggenbrot":                       "rye-bread",
    "broetchen-semmel":                 "buns-rolls",
    "toastbrot":                        "white-bread",
    "croissants-plunder":               "croissants",
    "aufbackware":                      "fresh-bread",
    "kekse-gebaeck":                    "cookies-biscuits",
    "kuchen-torten":                    "cakes",

    # ── Wurst, Fleisch, Eier & Fisch ───────────────────────────────────────
    "rind-kalb":                        "beef",
    "schweinefleisch":                  "pork",
    "lamm":                             "lamb",
    "huhn-pute":                        "poultry",
    "ente-gans":                        "poultry",
    "fleisch-sonstiges":                "fresh-meat",
    "hackfleisch":                      "ground-meat",
    "frischeier":                       "eggs",
    "jausen-farbeier":                  "eggs",
    "meeresfisch":                      "fresh-fish",
    "suesswasserfisch":                 "fresh-fish",
    "meeresfruechte":                   "shellfish",
    "kaviar-raeucherfisch-spezialitaeten": "canned-seafood",
    "dosenfische":                      "canned-seafood",
    "wurst-aufschnitt":                 "deli-meat",
    "schinken":                         "ham",
    "salami-speck":                     "salami",
    "bratwurst-wuerstchen":             "sausages",
    "frankfurter-wiener":               "hot-dogs",
    "leberkase-pasteten":               "processed-meat",

    # ── Milchprodukte & Alternativen ───────────────────────────────────────
    "vollmilch":                        "whole-milk",
    "fettarme-milch":                   "2-milk",
    "magermilch":                       "skim-milk",
    "pflanzenmilch":                    "plant-based-milk",
    "laktosefreie-milch":               "lactose-free",
    "hartkase":                         "block-cheese",
    "schnittkase":                      "sliced-cheese",
    "weichkase":                        "cream-cheese",
    "frischkase":                       "cream-cheese",
    "huettenkase":                      "cottage-cheese",
    "reibkase":                         "parmesan",
    "mozzarella":                       "mozzarella",
    "kase-sonstiger":                   "block-cheese",
    "joghurt":                          "regular-yogurt",
    "trinkjoghurt":                     "drinkable-yogurt",
    "pflanzlicher-joghurt":             "plant-based-yogurt",
    "butter":                           "butter-margarine",
    "margarine":                        "butter-margarine",
    "obers-sahne":                      "heavy-cream",
    "sauerrahm-creme-fraiche":          "sour-cream",
    "schlagobers":                      "whipped-cream",
    "milchalternativen":                "non-dairy-creamer",

    # ── Beilagen, Essig, Öl & Gewürze ─────────────────────────────────────
    "nudeln-teigwaren":                 "dry-pasta",
    "reis-huelsenfruechte":             "rice",
    "essig":                            "balsamic-vinegar",
    "speiseoel":                        "olive-oil",
    "dressings":                        "salad-dressing",
    "gewuerze-gewuerzoele":             "spices-seasonings",
    "getrocknete-kraeuter-pilze":       "mixed-spices",
    "speisesalz":                       "salt",
    "ketchup-senf-co":                  "ketchup",
    "pesto-sugo-saucen":                "pasta-sauce",
    "zucker-traubenzucker":             "sugar",
    "suessstoff-zuckerersatz":          "sugar",
    "backzutaten-tortendeko":           "baking",
    "backmischungen":                   "cake-mix",
    "mehl-griess-co":                   "flour",
    "marmelade-konfituere":             "sauces-condiments",
    "honig-sirup":                      "sauces-condiments",
    "nussmus-suesse-aufstriche":        "sauces-condiments",
    "muesli-cerealien":                 "oats",

    # ── Süßes & Salziges ───────────────────────────────────────────────────
    "zuckerl-kaugummi":                 "hard-candy",
    "wirkungsbonbons":                  "hard-candy",
    "schokolade-pralinen":              "chocolate-bars",
    "fruchtgummi-fruchtspeck":          "gummy-candy",
    "schoko-schaumzuckerware":          "candy-chocolate",
    "riegel":                           "granola-bars",
    "waffeln-kekse-co":                 "cookies-biscuits",
    "lebkuchen-saisonware":             "cookies-biscuits",
    "chips-snips-co":                   "potato-chips",
    "nuesse-kerne":                     "mixed-nuts",
    "knabbergebaeck":                   "chips-crisps",
    "popcorn":                          "popcorn",
    "nachos-dips":                      "tortilla-chips",
    "nuesse-kerne-trockenfruechte":     "nuts-trail-mix",

    # ── Schnelle Küche & To Go ─────────────────────────────────────────────
    "tk-fischfertiggerichte":           "frozen-meals",
    "tk-gemuesefertiggerichte":         "frozen-meals",
    "tk-traditionelle-fertiggerichte-saucen-suppen": "frozen-meals",
    "tk-fertiggerichte-aus-aller-welt": "frozen-meals",
    "suppen-einlagen":                  "canned-soup",
    "basis-fixgerichte":                "cooking-baking-mixes",
    "fertigmahlzeiten":                 "frozen-meals",
    "fertigteige-tiefgekuehlt":         "frozen-meals",
    "sonstige-fertigteige":             "bread-mix",
    "sonstige-fertiggerichte-to-go":    "frozen-meals",

    # ── Tiefkühlprodukte ───────────────────────────────────────────────────
    "tk-gemuese":                       "frozen-vegetables",
    "tk-kartoffelprodukte":             "frozen-snacks",
    "tk-obst":                          "frozen-fruits",
    "tk-fisch":                         "frozen-fish-fillets",
    "tk-fleisch":                       "frozen-chicken",
    "tk-pizza":                         "frozen-pizza",
    "tk-backwaren":                     "frozen-meals",
    "speiseeis-desserts":               "ice-cream",
    "eis-am-stiel":                     "popsicles",
    "eissandwich-waffeleis":            "ice-cream-sandwiches",

    # ── Babynahrung ────────────────────────────────────────────────────────
    "baby-glaskost":                    "baby-food",
    "milchfertignahrung":               "baby-formula",
    "saefte-tee":                       "baby-drinks",
    "fruechte-mischungen":              "baby-food",
    "menues":                           "baby-food",
    "breie":                            "baby-food",
    "desserts-snacks":                  "baby-food",

    # ── Alkoholfreie Getränke ──────────────────────────────────────────────
    "fruchtsaefte-nektare":             "juice",
    "fruchtsaefte-gespritzt":           "juice",
    "limonaden-cola":                   "soft-drinks-soda",
    "stille-getraenke":                 "bottled-water",
    "tonic-bitter-getraenke":           "soft-drinks-soda",
    "eistee-teegetraenke":              "iced-tea",
    "sirupe-konzentrate":               "soft-drinks-soda",
    "smoothies-gekuehlte-saefte":       "juice",
    "prickelnd":                        "sparkling-water",
    "mild":                             "bottled-water",
    "still":                            "bottled-water",
    "mineralwasser-mit-geschmack":      "flavored-water",
    "energy-drinks":                    "sports-energy-drinks",
    "eiskaffee":                        "coffee",
    "fluessige-isotonische-getraenke":  "sports-energy-drinks",
    "pulverfoermige-isotonische-getraenke": "sports-energy-drinks",
    "alkohlfreie-weine":                "soft-drinks-soda",
    "alkohlfreie-schaumweine":          "soft-drinks-soda",

    # ── Kaffee, Tee & Kakao ────────────────────────────────────────────────
    "kaffeebohnen":                     "whole-bean-coffee",
    "gemahlener-kaffee":                "ground-coffee",
    "kaffeekapseln-kaffeepads":         "coffee-pods",
    "loeskaffee":                       "instant-coffee",
    "malzkaffee-kaffeeersatz":          "instant-coffee",
    "gruener-weisser-tee":              "green-tea",
    "schwarztee":                       "black-tea",
    "kraeutertee":                      "herbal-tea",
    "fruechtetee":                      "herbal-tea",
    "teemischungen":                    "tea-bags",
    "kakao-pulver-fluessig":            "cocoa-powder",
    "kakao-sonstiger":                  "cocoa-powder",

    # ── Alkoholische Getränke ──────────────────────────────────────────────
    "traditionelles-bier":              "lager-pilsner",
    "weizenbier":                       "wheat-specialty-beer",
    "dunkles-bier":                     "stout-porter",
    "alkoholfreies-bier-leichtbier":    "non-alcoholic-beer",
    "radler-co":                        "hard-seltzer-cider",
    "biere-sonstige":                   "beer",
    "rotweine":                         "red-wine",
    "weissweine":                       "white-wine",
    "roseweine":                        "ros",
    "suess-dessertweine":               "desert-wine",
    "weinhaltige-getraenke":            "wine",
    "prosecco":                         "sparkling-wine",
    "champagner":                       "sparkling-wine",
    "sekt":                             "sparkling-wine",
    "spumante-frizzante":               "sparkling-wine",
    "cider":                            "hard-seltzer-cider",
    "andere-schaumweine":               "sparkling-wine",
    "whisk-e-y-bourbon":                "whiskey",
    "gin":                              "gin",
    "rum":                              "rum",
    "vodka":                            "vodka",
    "grappa":                           "spirits",
    "wermut-absinth":                   "spirits",
    "tequila-mezcal":                   "tequila",
    "weinbrand-cognac":                 "spirits",
    "schnaepse-braende":                "spirits",
    "likoere":                          "liqueurs",
    "bitter-getraenke":                 "spirits",
    "alkoholfreie-spirituosen":         "spirits",
    "premixes-mit-spirituosen":         "hard-seltzer-cider",
    "jagatee-punsch":                   "spirits",

    # ── Haarpflege ─────────────────────────────────────────────────────────
    "anti-schuppen-shampoo":            "shampoo",
    "medizinische-shampoos":            "shampoo",
    "color-shampoo":                    "shampoo",
    "trockenes-geschaedigtes-haar":     "shampoo",
    "haarspuelung":                     "conditioner",
    "haarkuren-masken":                 "conditioner",
    "haarwasser":                       "conditioner",
    "haargel":                          "shaving-grooming",
    "haarwachs":                        "shaving-grooming",
    "haarspray-haarlack":               "shaving-grooming",
    "stylingschaum-festiger":           "shaving-grooming",
    "permanent":                        "shaving-grooming",
    "semi-permanent":                   "shaving-grooming",
    "non-parmanent":                    "shaving-grooming",

    # ── Körperpflege ───────────────────────────────────────────────────────
    "seifen":                           "bar-soap",
    "duschgels-co":                     "body-wash",
    "badezusaetze":                     "bath-body",
    "gesichtsreinigung":                "bath-body",
    "gesichtspflege":                   "lotion",
    "bodylotion-hautcreme":             "lotion",
    "handcreme":                        "lotion",
    "lippenbalsam":                     "bath-body",
    "deo-spray":                        "bath-body",
    "roll-on":                          "bath-body",
    "deo-sticks":                       "bath-body",
    "deo-creme":                        "bath-body",
    "rasierer-zubehoer":                "razors",
    "rasierklingen":                    "razors",
    "rasierschaum-gel":                 "shaving-cream",
    "pre-aftershave":                   "shaving-cream",
    "enthaarungscreme-wachs":           "shaving-grooming",
    "sonnencreme-sprays":               "bath-body",
    "after-sun":                        "bath-body",
    "repellents":                       "bath-body",

    # ── Zahnpflege ─────────────────────────────────────────────────────────
    "zahnpasta-fuer-kinder":            "toothpaste",
    "zahnpasta-fuer-erwachsene":        "toothpaste",
    "mundspuelungen":                   "mouthwash",
    "handzahnbuersten-fuer-erwachsene": "toothbrushes",
    "handzahnbuersten-fuer-kinder":     "toothbrushes",
    "zahnseide":                        "dental-floss",
    "mundpflege":                       "oral-care",

    # ── Gesundheit ─────────────────────────────────────────────────────────
    "vitamine-minerialien":             "vitamins",
    "protein-sportnahrung":             "protein-powder",
    "pflaster":                         "first-aid",
    "verbaende-kompressen":             "first-aid",
    "kondome":                          "personal-care-health",
    "massageoele-einreibemittel":       "lotion",

    # ── Hygiene / Papierprodukte ───────────────────────────────────────────
    "taschentuecher-2-3-lagig":         "paper-products",
    "taschentuecher-4-lagig":           "paper-products",
    "kuechenrollen":                    "paper-towels",
    "toilettenpapier-feucht":           "wipes",
    "toilettenpapier-trocken":          "toilet-paper",
    "binden":                           "pads",
    "slipeinlagen":                     "liners",
    "tampons":                          "tampons",
    "intimpflege":                      "feminine-care",
    "inkontinenz":                      "personal-care-health",

    # ── Baby & Kids ────────────────────────────────────────────────────────
    "windeln":                          "diapers-wipes",
    "babytuecher":                      "diapers-wipes",
    "lotionen-cremen":                  "baby-food",
    "babyoel":                          "baby-food",
    "babypuder":                        "baby-food",
    "babyshampoo-reinigung":            "baby-food",

    # ── Household / Haushalt ───────────────────────────────────────────────
    "geschirrreiniger-zubehoer":        "dishwasher-detergent",
    "geschirrreiniger":                 "dish-soap",
    "haushaltsreiniger":                "cleaning-supplies",
    "haushaltsreiniger-generalisten":   "all-purpose-cleaner",
    "haushaltsreiniger-spezialisten":   "bathroom-cleaner",
    "wc-reiniger-steine":               "bathroom-cleaner",
    "wc-reiniger":                      "bathroom-cleaner",
    "luferterfrischer-raumduft":        "air-fresheners",
    "lufterfrischer":                   "air-fresheners",
    "reinigungssysteme":                "cleaning-supplies",
    "putzsysteme":                      "cleaning-supplies",
    "haushaltstuecher":                 "cleaning-supplies",
    "haushaltstuecher-schwaemme":       "cleaning-supplies",
    "waschmittel-weichspueler":         "laundry-detergent",
    "waschmittel":                      "laundry-detergent",
    "weichspueler":                     "fabric-softener",
    "textilpflege":                     "stain-removers",
    "textilpflege-zubehoer":            "dryer-sheets",
    "trocknen-buegeln":                 "dryer-sheets",
    "muellsaecke":                      "trash-bags",
    "jausen-tiefkuehlsaecke":           "zipper-bags",
    "sonstige-aufbewahrungssaecke":     "zipper-bags",
    "alufolien-bratfolien":             "aluminum-foil",
    "frischhaltefolien":                "plastic-wrap",
    "backpapier":                       "aluminum-foil",
    "aufbewahrung-dosen":               "food-storage-containers",
    "servietten-co":                    "napkins",
    "eimer-co":                         "cleaning-supplies",
    "haushaltshandschuhe-sonstiges":    "cleaning-supplies",
    "besen-buersten":                   "cleaning-supplies",

    # ── Pets ───────────────────────────────────────────────────────────────
    "hund":                             "dog-food",
    "katze":                            "cat-food",
    "vogel":                            "other-pet-supplies",
    "nager":                            "other-pet-supplies",
    "fisch":                            "other-pet-supplies",
    "heimtier-verbrauchsstoffe":        "other-pet-supplies",
}


# ── Browser helpers ────────────────────────────────────────────────────────────

def _rewarm_session(page):
    try:
        page.goto("https://www.spar.at", wait_until="domcontentloaded", timeout=20_000)
        page.wait_for_timeout(2_000)
        page.goto("https://www.spar.at/produktwelt/suche?search=&page=1",
                  wait_until="domcontentloaded", timeout=20_000)
        page.wait_for_timeout(3_000)
    except Exception:
        pass


def _browser_fetch(page, url: str) -> dict | None:
    import json as _json
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15_000)
        text = page.evaluate("document.body.innerText")
        if not text or not text.strip().startswith(("{", "[")):
            return None
        return _json.loads(text)
    except Exception:
        return None


def _fetch_category_node(page, slug: str) -> dict | None:
    url = f"https://{API_HOST}/ecom/pw/v1/category/v1/at/breadcrumb/{slug}"
    data = _browser_fetch(page, url)
    if not data or not isinstance(data, list):
        return None
    return data[-1]


def _walk_tree(page, slug: str, level: int = 1) -> list:
    node = _fetch_category_node(page, slug)
    if not node:
        return []
    children = node.get("childCategories") or []
    is_leaf = len(children) == 0
    result = [{"slug": slug, "level": level, "is_leaf": is_leaf}]
    for child in children:
        child_slug = child["categoryId"]
        time.sleep(0.15)
        result += _walk_tree(page, child_slug, level + 1)
    return result


def _search_products_in_category(page, slug: str, api_url_template: str) -> list:
    product_ids = []
    page_num = 1
    while True:
        url = (
            api_url_template
            .replace("{page}", str(page_num))
            + f"&filter=pwCategoryPathIDs%3A{slug}"
        ).replace("/search?", "/navigation?")
        data = _browser_fetch(page, url)
        if not data or not data.get("hits"):
            break
        for hit in data["hits"]:
            mv = hit.get("masterValues", {})
            pid = mv.get("productId")
            if pid:
                product_ids.append(str(pid))
        paging = data.get("paging", {})
        if page_num >= paging.get("pageCount", 1):
            break
        page_num += 1
        time.sleep(0.2)
    return product_ids


# ── DB helpers ─────────────────────────────────────────────────────────────────

_spar_url_map: dict = {}

def _ensure_url_map():
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


def _assign_category(spar_product_ids: list, category_id: int, dry_run: bool) -> int:
    if not spar_product_ids:
        return 0
    _ensure_url_map()
    product_ids = [_spar_url_map[s] for s in spar_product_ids if s in _spar_url_map]
    if not product_ids or dry_run:
        return len(product_ids)
    from sqlalchemy import text as _text
    for attempt in range(3):
        try:
            db.session.execute(
                _text("UPDATE products SET category_id = :cat WHERE id = ANY(:ids) AND (category_id IS NULL OR category_id != :cat)"),
                {"cat": category_id, "ids": product_ids},
            )
            return len(product_ids)
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
            print(f"      → {len(cats)} categories found, re-warming session…")
            _rewarm_session(page)
            time.sleep(1.0)

        leaf_cats = [c for c in all_cats if c["is_leaf"]]
        mappable = [c for c in leaf_cats if c["slug"] in SPAR_TO_OUR_SLUG]
        print(f"\n[✓] Found {len(leaf_cats)} leaf categories, {len(mappable)} have a mapping\n")

        with app.app_context():
            # Build our-slug → category_id lookup
            from models.postgres_models import Category
            our_cats = Category.query.all()
            slug_to_id = {c.slug: c.id for c in our_cats}
            print(f"[*] Loaded {len(slug_to_id)} website categories\n")

            # Re-warm before product search phase
            print("[*] Re-warming CF session before product search…")
            _rewarm_session(page)

            total_assigned = 0
            skipped = 0
            REWARM_EVERY = 25
            print("[*] Assigning categories to products…")

            for i, cat in enumerate(leaf_cats):
                slug = cat["slug"]
                our_slug = SPAR_TO_OUR_SLUG.get(slug)
                if not our_slug:
                    skipped += 1
                    continue

                cat_id = slug_to_id.get(our_slug)
                if not cat_id:
                    print(f"    [!] Our slug '{our_slug}' not found in DB — skipping {slug}")
                    skipped += 1
                    continue

                if i > 0 and i % REWARM_EVERY == 0:
                    print(f"\n[*] Re-warming CF session at category {i}…")
                    _rewarm_session(page)
                    print("[✓] Session refreshed\n")

                print(f"    {slug} → {our_slug}…", end=" ", flush=True)
                spar_ids = _search_products_in_category(page, slug, api_url_template)

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

                assigned = _assign_category(spar_ids, cat_id, dry_run)
                total_assigned += assigned
                print(f"{len(spar_ids)} SPAR products, {assigned} matched & assigned")

                if not dry_run and i % 10 == 0:
                    try:
                        db.session.commit()
                    except Exception:
                        db.session.rollback()

                time.sleep(1.0)

            if not dry_run:
                db.session.commit()
                print(f"\n[✓] Categories committed to DB")

        browser.close()

    print(f"\n{'='*60}")
    print(f"  Total products assigned categories: {total_assigned}")
    print(f"  SPAR categories without mapping:   {skipped}")
    print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
