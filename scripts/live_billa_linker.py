import sys, os, random, time, json, re
from datetime import datetime, UTC
from urllib.parse import urlparse

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from app import app
from utils.db import mongo
from scrapers.real_billa_scraper import RealBillaScraper

# Proper Billa logo - use a PNG from Billa's CDN that's more reliable than SVG
# Fallback: The template will show store name if image fails
BILLA_LOGO = "https://shop.billa.at/img/logo.png"

TOKEN_SYNONYMS = {
    # Fruit
    "apple": "apfel", "apples": "apfel",
    "banana": "bananen", "bananas": "bananen",
    "blueberries": "heidelbeeren", "blueberry": "heidelbeeren",
    "strawberries": "erdbeeren", "strawberry": "erdbeeren",
    "oranges": "orangen", "orange": "orangen",
    "pineapple": "ananas",
    "grapes": "trauben", "grape": "trauben",
    "lemon": "zitrone", "lemons": "zitronen",
    "raspberries": "himbeeren", "raspberry": "himbeeren",
    # Vegetables
    "broccoli": "brokkoli",
    "carrots": "karotten", "carrot": "karotten",
    "lettuce": "salat", "spinach": "spinat",
    "cucumber": "gurke",
    "pepper": "paprika", "peppers": "paprika",
    "onion": "zwiebel", "onions": "zwiebel",
    "potato": "erdapfel", "potatoes": "erdapfel",
    "tomato": "tomaten", "tomatoes": "tomaten",
    "mushroom": "champignons", "mushrooms": "champignons",
    "peas": "erbsen", "corn": "mais",
    # Dairy
    "milk": "milch", "butter": "butter",
    "cheese": "kaese", "mozzarella": "mozzarella",
    "yogurt": "joghurt", "yoghurt": "joghurt",
    "cream": "sahne", "eggs": "eier", "egg": "eier",
    # Bakery
    "bread": "brot",
    "roll": "semmel", "rolls": "semmeln",
    "bun": "semmel", "buns": "semmeln",
    "croissant": "croissant", "toast": "toast",
    # Meat
    "chicken": "huhn", "beef": "rindfleisch",
    "pork": "schweinefleisch", "sausage": "wurst",
    "ham": "schinken", "bacon": "speck",
    # Pantry
    "pasta": "pasta", "rice": "reis",
    "flour": "mehl", "sugar": "zucker",
    "salt": "salz", "oil": "oel",
    "coffee": "kaffee", "tea": "tee",
    "honey": "honig", "jam": "marmelade",
    "pizza": "pizza", "chips": "chips",
}

# Explicit German translations for multi-word phrases
EXTRA_QUERY_MAP = {
    "bread roll": ["semmel", "semmeln"],
    "bread rolls": ["semmeln", "semmel"],
    "chicken breast": ["huehnerbrust", "huehnerfilet"],
    "greek yogurt": ["griechisches joghurt"],
    "greek yoghurt": ["griechisches joghurt"],
    "olive oil": ["olivenoel"],
    "extra virgin olive oil": ["olivenoel extra vergine", "olivenoel"],
    "orange juice": ["orangensaft"],
    "whole milk": ["vollmilch"],
    "skim milk": ["magermilch"],
    "low fat milk": ["halbfettmilch"],
    "ciabatta": ["ciabatta"],
    "pizza dough": ["pizzateig"],
}

STOPWORDS = {
    "with", "and", "the", "for", "per", "kg", "pack", "pieces", "piece",
    "fresh", "organic", "classic", "instant", "high", "protein", "maxipack",
    "whole", "grain", "long", "life", "shelf", "stable", "natural",
    "500ml", "1000ml", "250ml", "100ml", "1ltr", "1liter", "750ml",
    "1kg", "500g", "250g", "100g",
}

# Used to block cross-category matches (e.g., Apple fruit -> Apple Cider)
BILLA_BEVERAGE_WORDS = {"cider", "saft", "juice", "wein", "wine", "bier", "beer",
                        "limonade", "cola", "energy", "getraenk", "drink", "zero", "light",
                        "rauch", "yippy", "malibu", "strongbow", "arizona", "red bull",
                        "voeslauer", "vöslauer", "almdudler", "schweppes", "fanta", "sprite",
                        "capri", "aqua", "wasser", "porto", "emission", "emotion",
                        "active o2", "active", "roemer", "roemerquelle", "gasteiner",
                        "grapes reserve"}
PRODUCE_KEYWORDS = {"apple", "apfel", "orange", "orangen", "grape", "trauben",
                    "pineapple", "ananas", "lemon", "zitrone", "cherry", "kirschen",
                    "strawberr", "erdbeere", "blueberr", "heidelbeer", "raspberry", "himbeer",
                    "banana", "banane", "carrot", "karotte", "spinach", "spinat",
                    "tomato", "tomate", "cucumber", "gurke", "broccoli", "brokkoli"}

# Pet food brand and indicator words — never match grocery items to these
PET_FOOD_WORDS = {"zooroyal", "royalcanin", "whiskas", "felix cat", "animonda",
                  "pastete", "tiernahrung", "katze", "hunde", "hundefutter",
                  "katzenfutter", "hundesnack", "katzennassfutter"}

# Confectionery / candy words — should not match fresh produce
CANDY_WORDS = {"trolli", "haribo", "nimm2", "gummibear", "gummibaer", "bonbon",
               "saure", "fruchtgummi", "schokoriegel", "schokolade", "candy",
               "kaugummi", "lutscher"}

# Milk variant words that should not replace standard dairy milk.
NON_STANDARD_MILK_WORDS = {
    "buttermilch", "kokosmilch", "mandelmilch", "hafermilch", "reismilch", "sojamilch",
    "haferdrink", "mandeldrink", "sojadrink", "reisdrink"
}


def _extract_fat_pct(text):
    """Extract fat% from label like 'Milk 0.9%' -> 0.9, or None."""
    text = text.replace(",", ".")
    m = re.search(r"(\d+\.?\d*)\s*%", text)
    return float(m.group(1)) if m else None


def _extract_size(text):
    """Extract size/quantity indicator from product name.
    E.g., 'Eggs 10 Pack' -> 10, '6er' -> 6, '500ml' -> 500, etc.
    Returns a tuple (quantity, unit) like (10, 'pieces') or (500, 'ml') or None."""
    text_lower = text.lower()
    
    # Match patterns like "10 pack", "6er", "500ml", "1l", "250g", etc.
    patterns = [
        (r'(\d+)\s*pack', 'pieces'),           # "10 pack" -> (10, pieces)
        (r'(\d+)(er|ers?)\b', 'pieces'),       # "6er", "6ers" -> (6, pieces)
        (r'(\d+)\s*x\s*(\d+)(\w+)', 'combo'),  # "6 x 100g" -> size
        (r'(\d+)\s*(ml|l|mliter|liter)', 'ml'),  # "500ml", "1l" -> (500, ml)
        (r'(\d+)\s*([gk]g)', 'g'),             # "250g", "1kg" -> (250, g)
    ]
    
    for pattern, unit in patterns:
        m = re.search(pattern, text_lower)
        if m:
            qty = int(m.group(1))
            # Normalize units
            if unit == 'ml' and 'l' in text_lower and 'ml' not in text_lower.replace('liter', ''):
                qty *= 1000  # 1l -> 1000ml
            return (qty, unit)
    return None


def _size_similarity(spar_size, billa_size):
    """Score size match: 1.0 if exact, 0.5-0.8 if within 20%, 0 otherwise."""
    if spar_size is None or billa_size is None:
        return 0.0
    s_qty, s_unit = spar_size
    b_qty, b_unit = billa_size
    # Different units = no match
    if s_unit != b_unit:
        return 0.0
    # Same size = perfect match
    if s_qty == b_qty:
        return 1.0
    # Within 20% tolerance (e.g., 10 vs 6 pieces is 60%, no match)
    ratio = min(s_qty, b_qty) / max(s_qty, b_qty)
    if ratio >= 0.8:  # Within 20%
        return 0.8
    return 0.0


def _normalize_tokens(text):
    # Normalize German umlauts so ö/oe, ü/ue, ä/ae, ß/ss all match
    text = text.lower().replace("-", " ")
    text = text.replace("ö", "oe").replace("ü", "ue").replace("ä", "ae").replace("ß", "ss")
    toks = re.findall(r"[a-zA-Z0-9]+", text)
    out = []
    for t in toks:
        if len(t) <= 2 or t in STOPWORDS:
            continue
        norm = TOKEN_SYNONYMS.get(t, t)
        out.append(norm)
        # Split common compound dairy tokens so "leichtmilch" can match "milch".
        if norm.endswith("milch") and norm != "milch":
            out.append("milch")
        if norm.endswith("eier") and norm != "eier":
            out.append("eier")
    return out


def _is_cross_category(spar_name, billa_name):
    """Block fruit/veg spar items from matching beverages, pet food, candy, or processed food."""
    s, b = spar_name.lower(), billa_name.lower()
    is_produce_query = any(p in s for p in PRODUCE_KEYWORDS)
    if is_produce_query:
        if any(bw in b for bw in BILLA_BEVERAGE_WORDS):
            return True
        if any(pw in b for pw in PET_FOOD_WORDS):
            return True
        if any(cw in b for cw in CANDY_WORDS):
            return True
        # For single-word produce names, block processed food results
        spar_words = s.strip().split()
        is_simple_produce = len(spar_words) <= 2
        PROCESSED_INDICATORS = {"joghurt", "tortelloni", "pasta", "suppe", "soup",
                                 "smoothie", "marmelade", "saft", "sorbet",
                                 "wasser", "nektar", "sirup", "konfituere", "mus",
                                 "puree", "passiert", "doppelt", "fein", "creme",
                                 "konserve", "dose", "frozen", "tiefgefroren", "gefroren"}
        if is_simple_produce and any(pi in b for pi in PROCESSED_INDICATORS):
            return True
    # Block any SPAR item from matching pet food
    if any(pw in b for pw in PET_FOOD_WORDS):
        return True
    return False


def _is_incompatible_milk_variant(spar_name, billa_name):
    """Block substitutions like milk -> buttermilk/coconut milk/oat milk."""
    s = spar_name.lower()
    b = billa_name.lower()
    is_milk_query = ("milk" in s) or ("milch" in s)
    is_source_non_standard = any(w in s for w in NON_STANDARD_MILK_WORDS)
    if not is_milk_query or is_source_non_standard:
        return False
    return any(w in b for w in NON_STANDARD_MILK_WORDS)


def match_confidence(spar_name, billa_name):
    """Token-overlap score plus fat-% bonus/penalty for dairy."""
    st = set(_normalize_tokens(spar_name))
    bt = set(_normalize_tokens(billa_name))
    if not st or not bt:
        return 0.0
    base = len(st & bt) / max(1, len(st))
    sf, bf = _extract_fat_pct(spar_name), _extract_fat_pct(billa_name)
    if sf is not None and bf is not None:
        base = min(1.0, base + 0.3) if abs(sf - bf) < 0.05 else max(0.0, base - 0.4)
    return base


def build_queries(spar_name):
    """Build list of search queries from most to least specific, in German."""
    name_lower = spar_name.lower()
    extra = []
    for phrase, de_list in EXTRA_QUERY_MAP.items():
        if phrase in name_lower:
            extra.extend(de_list)
    tokens = _normalize_tokens(spar_name)
    queries = list(extra)
    if tokens:
        queries += [" ".join(tokens[:3]), " ".join(tokens[:2]), " ".join(tokens[:1])]
    queries.append(" ".join(spar_name.split()[:2]))
    seen, dedup = set(), []
    for q in queries:
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            dedup.append(q)
    return dedup


def pick_best_candidate(spar_name, candidates):
    """Return (best, score). Use size matching, then cheapest price as tiebreaker."""
    spar_size = _extract_size(spar_name)
    spar_fat = _extract_fat_pct(spar_name)
    scored = []
    for c in candidates:
        billa_name = c.get("name", "")
        if _is_cross_category(spar_name, billa_name):
            continue
        if _is_incompatible_milk_variant(spar_name, billa_name):
            continue

        score = match_confidence(spar_name, billa_name)

        # Size matching: when both products expose size, mismatches are blocked.
        billa_size = _extract_size(billa_name)
        size_score = _size_similarity(spar_size, billa_size)
        if spar_size and billa_size:
            if size_score == 0.0:
                continue
            if size_score >= 0.8:
                score = min(1.0, score + 0.2)
            else:
                score = max(0.0, score - 0.15)
        elif spar_size and not billa_size:
            score = max(0.0, score - 0.1)

        # Dairy-specific hard check to avoid wrong-fat substitutions.
        billa_fat = _extract_fat_pct(billa_name)
        if spar_fat is not None and billa_fat is not None and abs(spar_fat - billa_fat) > 0.05:
            continue

        price = float(c.get("price") or 9999)
        scored.append((score, size_score, price, c))
    
    if not scored:
        return None, 0.0

    # Pick the cheapest candidate among near-equal confidence matches.
    max_score = max(s[0] for s in scored)
    close_band = [s for s in scored if s[0] >= (max_score - 0.12)]
    close_band.sort(key=lambda x: (x[2], -x[1], -x[0]))
    best_score, _, _, best_c = close_band[0]
    return best_c, best_score
def find_cheaper_alternative(spar_name, initial_best, fast_search, min_confidence=0.65):
    """After finding a good match, search for cheaper alternatives of similar category.
    
    This helps avoid suboptimal matches like picking nöm €1.79 milk when Clever €1.59 exists.
    """
    initial_price = float(initial_best.get("price") or 9999)
    
    # Don't bother if initial match is very cheap
    if initial_price < 1.5:
        return initial_best
    
    # Extract key terms from spar name (e.g., "Milk", "0.9%")
    tokens = _normalize_tokens(spar_name)
    token_set = set(tokens)
    # Restrict this path to dairy/eggs to avoid cross-category regressions.
    if not ({"milch", "eier"} & token_set):
        return initial_best

    fat_pct = _extract_fat_pct(spar_name)
    
    # Build "find cheapest" queries
    cheaper_queries = []
    if tokens:
        cheaper_queries.append(" ".join(tokens))  # Full token search
    if fat_pct is not None:
        cheaper_queries.append(f"{' '.join(tokens[:2])} {fat_pct}%")  # With fat %
    if "milch" in token_set and fat_pct is not None and fat_pct <= 1.0:
        cheaper_queries.append("leichtmilch")
    
    all_alternatives = []
    seen = {initial_best.get("url")}  # Don't re-match the initial best
    
    for q in cheaper_queries:
        if not q or len(q) < 3:
            continue
        for alt in fast_search.search_products(q):
            if alt.get("url") not in seen:
                seen.add(alt.get("url"))
                all_alternatives.append(alt)
        if len(all_alternatives) > 50:
            break  # Don't search too much
    
    if not all_alternatives:
        return initial_best
    
    # Reuse core candidate logic for each alternative to enforce category/size/fat rules.
    valid_alts = []
    for alt in all_alternatives:
        cand, alt_score = pick_best_candidate(spar_name, [alt])
        if not cand or alt_score < min_confidence:
            continue
        valid_alts.append((float(cand.get("price") or 9999), alt_score, cand))
    
    if not valid_alts:
        return initial_best
    
    # Prefer cheaper alternatives that still pass confidence threshold.
    valid_alts.sort(key=lambda x: (x[0], -x[1]))
    for price, score, alt in valid_alts:
        cheaper_by = initial_price - price
        if cheaper_by > 0.10:  # At least 10 cents cheaper
            print(f"    cheaper alt: {alt.get('name')} @ EUR{price:.2f} (save EUR{cheaper_by:.2f})")
            return alt
    
    return initial_best

def link_billa_products():
    print("Billa Live Data Linker v2 starting...")
    fast_search = RealBillaScraper()
    success_logs, skip_logs, mapping_rows = [], [], []

    logs_dir = os.path.join(parent_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(logs_dir, f"billa_link_mappings_{stamp}.json")

    with app.app_context():
        products = list(mongo.db.products.find())
        print(f"Total products: {len(products)}")

        for idx, prod in enumerate(products):
            spar_name = prod.get("name", "")
            print(f"\n[{idx+1}/{len(products)}] {spar_name}")

            # Check if already linked and whether the entry has a product image
            existing_billa = next(
                (s for s in prod.get("stores", [])
                 if s.get("store") == "BILLA" and "billa.at" in urlparse(s.get("url", "")).netloc),
                None
            )
            needs_image = existing_billa is not None and not existing_billa.get("image")
            if existing_billa and not needs_image:
                print("  already linked + has image, skip")
                mapping_rows.append({"spar_name": spar_name, "status": "skipped_already_linked"})
                continue

            # ── Search ──────────────────────────────────────────────────────
            queries = build_queries(spar_name)
            all_results, query_used = [], ""
            seen_urls = set()
            for query in queries:
                print(f"  search: '{query}'")
                for r in fast_search.search_products(query):
                    if r["url"] not in seen_urls:
                        seen_urls.add(r["url"])
                        all_results.append(r)
                if all_results:
                    query_used = query

            if not all_results:
                print("  no results")
                skip_logs.append(f"no results: {spar_name}")
                mapping_rows.append({"spar_name": spar_name, "queries": queries,
                                     "status": "skipped_no_results"})
                continue

            # ── Pick best candidate ─────────────────────────────────────────
            best, conf = pick_best_candidate(spar_name, all_results)
            if not best:
                mapping_rows.append({"spar_name": spar_name, "queries": queries,
                                     "status": "skipped_no_candidate"})
                continue

            billa_name  = best.get("name", "")
            billa_url   = best.get("url", "")
            billa_price = best.get("price", 0)
            billa_image = best.get("image_url", "") or ""
            billa_offer = best.get("offer")
            in_promo    = best.get("in_promotion", False)
            billa_unit = best.get("unit") or ""
            confirm_ts = best.get("price_confirmed_at") or datetime.now(UTC).isoformat()

            # ── Find cheaper alternative ────────────────────────────────
            if conf >= 0.60:  # Only search for cheaper if at least decent match found
                cheaper = find_cheaper_alternative(spar_name, best, fast_search)
                if cheaper.get("url") != best.get("url"):
                    best, conf = cheaper, match_confidence(spar_name, cheaper.get("name", ""))
                    billa_name = cheaper.get("name", "")
                    billa_url = cheaper.get("url", "")
                    billa_price = cheaper.get("price", 0)
                    billa_image = cheaper.get("image_url", "") or ""
                    billa_offer = cheaper.get("offer")
                    in_promo = cheaper.get("in_promotion", False)
                    billa_unit = cheaper.get("unit") or billa_unit
                    confirm_ts = cheaper.get("price_confirmed_at") or confirm_ts
                    print(f"  -> using cheaper option @ EUR{billa_price:.2f}")

            THRESHOLD = 0.55
            if conf < THRESHOLD:
                print(f"  low conf ({conf:.2f}): '{billa_name}' skip")
                skip_logs.append(f"low conf ({conf:.2f}): {spar_name} != {billa_name}")
                mapping_rows.append({
                    "spar_name": spar_name, "queries": queries,
                    "candidate_billa_name": billa_name, "candidate_billa_url": billa_url,
                    "confidence": round(conf, 3), "status": "skipped_low_confidence",
                })
                continue

            print(f"  MATCH ({conf:.2f}) -> '{billa_name}' @ EUR{billa_price:.2f}"
                  f"  img={'yes' if billa_image else 'no'}  offer={bool(billa_offer)}")

            try:
                if existing_billa:
                    # Update existing BILLA entry: add image and offer data
                    update_set = {
                        "stores.$.logo": BILLA_LOGO,
                        "stores.$.price": billa_price,
                        "stores.$.url": billa_url,
                        "stores.$.updated_at": confirm_ts,
                        "stores.$.price_confirmed_at": confirm_ts,
                        "updated_at": confirm_ts,
                    }
                    if billa_image:
                        update_set["stores.$.image"] = billa_image
                    if billa_offer:
                        update_set["stores.$.offer"] = billa_offer
                    if in_promo:
                        update_set["stores.$.in_promotion"] = True
                    if billa_unit:
                        update_set["stores.$.unit"] = billa_unit
                        if not (prod.get("unit") or "").strip():
                            update_set["unit"] = billa_unit

                    # Recompute cheapest using current product stores and fresh BILLA price.
                    refreshed_stores = []
                    for s in (prod.get("stores") or []):
                        entry = dict(s)
                        if entry.get("store") == "BILLA":
                            entry["price"] = billa_price
                        refreshed_stores.append(entry)
                    if refreshed_stores:
                        cheapest = min(refreshed_stores, key=lambda x: float(x.get("price") or 9999))
                        update_set["cheapest"] = {
                            "store": cheapest.get("store"),
                            "price": cheapest.get("price"),
                            "updated": confirm_ts,
                        }

                    mongo.db.products.update_one(
                        {"_id": prod["_id"], "stores.store": "BILLA"},
                        {"$set": update_set}
                    )
                    msg = f"UPDATED: {spar_name} -> {billa_name}"
                    success_logs.append(msg)
                    mapping_rows.append({
                        "spar_name": spar_name, "query": query_used,
                        "candidate_billa_name": billa_name, "billa_url": billa_url,
                        "confidence": round(conf, 3), "price": billa_price,
                        "image": billa_image, "offer": str(billa_offer),
                        "status": "updated_image",
                    })
                else:
                    # New BILLA link — always add-only
                    doc = {
                        "store": "BILLA", "price": billa_price, "url": billa_url,
                        "logo": BILLA_LOGO, "image": billa_image or None,
                        "unit": billa_unit or None,
                        "updated_at": confirm_ts,
                        "price_confirmed_at": confirm_ts,
                    }
                    if billa_offer:
                        doc["offer"] = billa_offer
                    if in_promo:
                        doc["in_promotion"] = True
                    candidate_stores = prod.get("stores", []) + [doc]
                    cheapest = min(candidate_stores, key=lambda x: float(x.get("price") or 9999))
                    mongo.db.products.update_one(
                        {"_id": prod["_id"]},
                        {
                            "$push": {"stores": doc},
                            "$set": {
                                "cheapest": {
                                    "store": cheapest["store"],
                                    "price": cheapest["price"],
                                    "updated": confirm_ts,
                                },
                                "updated_at": confirm_ts,
                                **({"unit": billa_unit} if (billa_unit and not (prod.get("unit") or "").strip()) else {}),
                            }
                        }
                    )
                    msg = f"LINKED: {spar_name} -> {billa_name} @ EUR{billa_price:.2f}"
                    success_logs.append(msg)
                    mapping_rows.append({
                        "spar_name": spar_name, "query": query_used,
                        "candidate_billa_name": billa_name, "billa_url": billa_url,
                        "confidence": round(conf, 3), "price": billa_price,
                        "image": billa_image, "offer": str(billa_offer),
                        "status": "linked",
                    })
                print("  >>> " + msg)
            except Exception as e:
                print(f"  DB error: {e}")
                mapping_rows.append({"spar_name": spar_name, "status": "error", "error": str(e)})

            time.sleep(random.uniform(1.2, 2.5))

    print("\n" + "=" * 60)
    print(f"Done. Succeeded={len(success_logs)}  Skipped={len(skip_logs)}")
    for l in success_logs: print(" +", l)
    for l in skip_logs:    print(" -", l)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(mapping_rows, f, indent=2, ensure_ascii=False)
    print(f"Log -> {log_path}")


if __name__ == "__main__":
    link_billa_products()
