"""
Recipe ingredient matcher.

Architecture:
  1. Clean the raw ingredient string (strip quantities/units/adjectives)
  2. Classify the ingredient into a semantic type (fresh_produce, protein, condiment, etc.)
  3. Search the DB using the cleaned term
  4. Hard-filter candidates:
       - word-boundary check  (mirin ≠ mirinda)
       - non-food product check  (bamboo mat ≠ sushi rice)
       - junk category check  (beverages, snacks, household...)
       - type-aware name check  (soda/candy/beer/... for food ingredients)
       - flavor-suffix check  ("Cheese & Onion" → onion is a flavor, not the product)
  5. Score remaining candidates and return top 3
  6. If Gemini API key is available, run a single batch relevance-check pass
     across all ingredient→product pairs to catch anything the rules missed.
"""

import re
import os
import json
import requests
from models.postgres_models import Product, ProductStore, Store, Category

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

# German/English words that mark a product as a kitchen utensil or non-food item
NON_FOOD_PRODUCT_WORDS = {
    "matte", "bambusmatte", "bambus", "brett", "schneidebrett",
    "pfanne", "topf", "kochtopf", "messer", "sieb", "reibe",
    "werkzeug", "besteck", "schüssel", "schale", "aufkleber",
    "sticker", "deko", "dekor", "spielzeug",
    "toilettenpapier", "küchenrolle", "taschentuch", "windel",
    "reiniger", "spülmittel", "waschmittel", "putzmittel",
    "tablette", "tablet",          # cleaning tablets
    "beutel",                       # bags/pouches (non-food context)
    "für sushi",                    # "for sushi" → accessory, not food
    "für pizza",
    "rolle",                        # roll (as in toilet roll)
}

# DB category slugs whose root is always non-food
JUNK_SLUG_ROOTS = {
    "cat_beverages", "cat_snacks", "cat_household",
    "cat_baby-food", "cat_fast-food-to-go",
    "cat_pet", "cat_pets", "cat_tiernahrung", "cat_tierfutter",
}

JUNK_CATEGORY_NAMES = {
    "snacks", "beverages", "household", "baby food", "fast food & to go",
    "ready meals", "frozen meals", "sweets & treats", "sweets", "confectionery",
    "desserts", "ice cream", "biscuits", "cookies", "snacks & sweets",
    "household & cleaning", "baby & kids",
    "soft drinks", "alcoholic beverages", "beer", "wine & spirits",
    "energy drinks", "juices", "hot drinks", "drinks", "beverages & drinks",
    "candy", "chocolate", "gummies", "chips & crisps", "crackers", "popcorn",
    # Pet food
    "pet food", "pet", "pets", "cat food", "dog food", "animal food",
    "tiernahrung", "tierfutter", "katzenfutter", "hundefutter", "haustier",
    "haustiere", "haustierzubehör",
    # German
    "süßigkeiten", "getränke", "alkoholische getränke", "haushalt",
    "limonaden", "säfte", "erfrischungsgetränke",
}

# Product name keywords that always signal "not a cooking ingredient"
# (unless the searched ingredient IS that kind of product)
GLOBAL_NEGATIVE_NAME_KEYWORDS = {
    "beer", "ale", "lager", "stout", "pilsner", "weizen", "ipa", "pils",
    "soda", "cola",
    "gummy", "gummies", "candy", "haribo", "trolli", "chewy",
    "flavour", "flavored", "flavoured",
    "vodka", "whiskey", "gin", "rum", "tequila", "brandy", "schnapps", "liqueur",
    "cocktail", "cheeseburger", "sugarfree", "sugar-free", "zuckerfrei",
    "smoothie", "energy",   # energy drinks, smoothies are never cooking ingredients
    # Pet / animal food — never a cooking ingredient
    "katze", "katzenfutter", "katzensnack", "katzennahrung",
    "hund", "hundefutter", "hundesnack", "hundenahr",
    "tiernahrung", "tierfutter", "haustier",
    "für katzen", "für hunde", "for cats", "for dogs",
    "whiskas", "felix", "purina", "pedigree", "royal canin", "iams", "friskies",
    "sheba", "dreamies", "animonda", "almo nature",
    "aquarium", "vogelfutter", "hamster", "kaninchen", "meerschwein",
}

# Per-ingredient additional blocked substrings
INGREDIENT_NEGATIVE_KEYWORDS = {
    "mushroom": ["sour", "candy", "gummy", "sweet", "haribo"],
    "ginger":   ["beer", "ale", "brew", "snap", "biscuit", "cookie", "soda"],
    "garlic":   ["bruschett", "crouton", "chip", "crisp", "bagel"],
    "salt":     ["chips", "crisps", "peanuts", "nuts", "pretzel", "crackers", "popcorn"],
    "butter":   ["peanut", "almond", "cashew", "cacao", "cocoa", "cookie", "cake", "croissant"],
    "rice":     ["cake", "cakes", "cracker", "crisp", "pudding"],
    "milk":     ["chocolate", "condensed", "biscuit", "cookie"],
    "oil":      ["chips", "crisps"],
    "water":    ["melon"],
    "lemon":    ["soda", "squash", "cordial"],
    "lime":     ["soda", "cordial"],
    "apple":    ["cider"],
    "tomato":   ["cocktail"],
    "onion":    ["rings", "chip", "crisp"],
    "corn":     ["chip", "crisp", "popcorn"],
    "potato":   ["chip", "crisp"],
    "sugar":    ["sugarfree", "sugar-free", "zuckerfrei", "energy"],
    "pork":     ["cheeseburger", "burger", "cordon", "nugget", "schnitzel", "chip", "crisp", "rind"],
    "beef":     ["cheeseburger", "burger", "schnitzel", "nugget", "hotdog", "chip", "crisp"],
    "chicken":  ["cheeseburger", "burger", "schnitzel", "nugget", "crisp", "chip"],
    "mince":    ["cheeseburger", "burger"],
    "cream":    ["chocolate", "candy"],
    "coconut":  ["candy", "chocolate"],
    "carrot":   ["cake", "candy"],
    "spinach":  ["chip", "crisp"],
    "cheese":   ["mozzarella", "parmesan", "cheddar", "gouda", "brie", "swiss", "emmenthal",
                 "ricotta", "feta", "blue", "goat", "cottage", "mascarpone", "provolone",
                 "edam", "camembert", "pecorino", "havarti", "gruyere", "halloumi"],
}

# Single words that cannot identify a food product on their own.
# Never use these as the sole term in a fallback search — they produce
# nonsense matches (e.g. "Red" → "Red Bull", "Yellow" → "Yellow Smoothie").
INGREDIENT_MODIFIER_WORDS = frozenset({
    # Colours
    "red", "green", "yellow", "orange", "purple", "blue", "white", "black",
    "brown", "pink", "golden", "gold",
    # Shade / intensity
    "dark", "light", "bright", "pale", "deep",
    # Temperature / flavour
    "hot", "cold", "warm", "cool", "spicy", "mild", "sweet", "sour",
    # Size
    "big", "small", "large", "medium", "mini", "giant", "jumbo",
    # Preparation states (overlap with fillers, but guard the fallback path too)
    "sliced", "chopped", "diced", "minced", "grated",
    "raw", "cooked", "baked", "fried", "grilled", "roasted",
})

# Ingredient words that ARE the snack/drink — don't filter their matching products
INGREDIENT_IS_DRINK_OR_SNACK = {
    "beer", "wine", "cider", "juice", "soda", "water", "cola", "chocolate",
    "cookie", "chips", "crisps", "candy", "snack",
}

# ── Semantic ingredient type classification ───────────────────────────────────
# Maps ingredient type → list of core keywords.  First match wins.
INGREDIENT_TYPE_MAP = [
    ("fresh_produce", [
        "mushroom", "tomato", "onion", "shallot", "garlic", "carrot", "potato",
        "pepper", "celery", "broccoli", "spinach", "lettuce", "cucumber", "zucchini",
        "aubergine", "eggplant", "cauliflower", "leek", "asparagus", "corn",
        "peas", "green bean", "lentil", "chickpea", "apple", "pear", "lemon",
        "lime", "orange", "banana", "strawberry", "mango", "avocado", "kale",
        "cabbage", "beet", "radish", "pumpkin", "squash", "artichoke", "fennel",
        "spring onion", "scallion", "ginger", "turmeric root", "pak choi",
        "bok choy", "chilli", "chili",
    ]),
    ("grain_starch", [
        "rice", "pasta", "noodle", "flour", "oats", "barley", "quinoa",
        "couscous", "polenta", "breadcrumb", "panko", "tortilla", "sushi rice",
        "arborio", "jasmine rice", "basmati", "vermicelli", "udon", "soba",
        "rice paper", "wonton", "dumpling wrapper", "spring roll wrapper",
    ]),
    ("protein", [
        "pork", "beef", "chicken", "turkey", "lamb", "duck", "veal",
        "fish", "salmon", "tuna", "cod", "sea bass", "trout", "mackerel",
        "shrimp", "prawn", "crab", "lobster", "squid", "octopus",
        "tofu", "tempeh", "seitan", "egg", "minced meat", "ground beef",
        "ground pork", "sausage",
    ]),
    ("dairy", [
        "milk", "cream", "butter", "cheese", "yogurt", "yoghurt", "sour cream",
        "creme fraiche", "mascarpone", "ricotta", "parmesan", "mozzarella",
        "heavy cream", "double cream", "whipping cream", "condensed milk",
    ]),
    ("condiment", [
        "soy sauce", "mirin", "fish sauce", "oyster sauce", "hoisin", "teriyaki",
        "worcestershire", "vinegar", "balsamic", "ketchup", "mayo", "mayonnaise",
        "mustard", "tahini", "miso", "sriracha", "hot sauce",
        "olive oil", "sesame oil", "coconut oil", "vegetable oil", "sunflower oil",
        "coconut milk", "coconut cream", "stock", "broth", "vegetable broth",
        "chicken broth", "beef broth", "fish broth", "dashi",
        "tomato sauce", "tomato paste", "tomato puree", "passata",
    ]),
    ("seasoning", [
        "salt", "pepper", "black pepper", "white pepper", "cumin", "paprika",
        "turmeric", "cinnamon", "oregano", "thyme", "rosemary", "bay leaf",
        "cardamom", "nutmeg", "allspice", "star anise", "curry powder",
        "chili powder", "red pepper flake", "cayenne", "vanilla",
        "sugar", "brown sugar", "honey", "maple syrup", "sesame seed",
        "poppy seed",
    ]),
]

# For these types, we allow some snack-category products (e.g. condiments can overlap)
LENIENT_INGREDIENT_TYPES = {"condiment", "seasoning", "other_food"}

# Ingredient types where matching must be strict — the search term must be the
# primary product, not a secondary descriptor (e.g. "butter" in "apple butter").
STRICT_INGREDIENT_TYPES = frozenset({"fresh_produce", "grain_starch", "protein", "dairy"})

# All single words extracted from INGREDIENT_TYPE_MAP — used to detect when a
# known food word precedes the search term in a product name, signalling a
# compound product (e.g. "apple" before "butter" → apple-butter, not plain butter).
_FOOD_PREFIX_WORDS: frozenset = frozenset(
    word
    for _, keywords in INGREDIENT_TYPE_MAP
    for phrase in keywords
    for word in phrase.lower().split()
    if len(word) >= 4
)

# ── Category allowlist ────────────────────────────────────────────────────────
# For each ingredient type, at least ONE of these substrings must appear in
# the product's category slug + name_en + name_de string.
# None = no restriction (any category is accepted).
# Products with NO assigned category always pass (can't filter what isn't set).
# Only applied to types with reliable category boundaries; condiment/seasoning/
# other_food are left unrestricted to avoid false negatives with exotic slugs.
INGREDIENT_TYPE_CATEGORY_ALLOWLIST: dict[str, frozenset | None] = {
    # Produce & fresh items: must be in produce or frozen-veg branch
    "fresh_produce": frozenset({
        "cat_produce",          # cat_produce_fruits, cat_produce_vegetables …
        "cat_frozen",           # frozen vegetables are valid cooking ingredients
        "produce", "fruit", "vegetable", "frisch", "fresh",
        "obst", "gemüse", "gemuse", "pilz", "salat", "kräuter",
    }),
    # Grains, pasta, flour, bread: must be in pantry or bakery branch
    "grain_starch": frozenset({
        "cat_pantry",           # cat_pantry_rice, cat_pantry_pasta, cat_pantry_flour …
        "cat_bakery",           # bread, rolls, breadcrumbs
        "pantry", "grain", "cereal", "bakery", "bread",
        "reis", "pasta", "nudel", "mehl",
    }),
    # Meat, fish, eggs, tofu: must be in meat branch (covers poultry, seafood, deli)
    # or frozen (frozen fish/meat), or dairy_eggs (eggs classified there)
    "protein": frozenset({
        "cat_meat",             # cat_meat_fresh-meat, cat_meat_poultry, cat_meat_seafood …
        "cat_dairy_eggs",       # eggs
        "cat_frozen",           # frozen fish / meat products OK as ingredients
        "meat", "fleisch", "fish", "fisch", "seafood", "poultry",
        "geflügel", "egg", "ei", "deli", "wurst", "tofu",
    }),
    # Dairy: must be in dairy branch
    "dairy": frozenset({
        "cat_dairy",            # cat_dairy_milk, cat_dairy_cheese, cat_dairy_butter …
        "dairy", "milch", "milk", "käse", "kase", "cheese", "butter",
        "yogurt", "joghurt", "sahne", "cream", "quark", "molkerei",
    }),
    # Condiments, seasonings, other: no allowlist (categories too varied across stores)
    "condiment": None,
    "seasoning":  None,
    "other_food": None,
}

# ── Ingredient substitution rules ─────────────────────────────────────────────
# Explicit swaps used as a fallback before calling Gemini for alternatives.
# Key = canonical ingredient name (lower-cased), value = ordered list of
# acceptable substitutes (most preferred first).
INGREDIENT_SUBSTITUTIONS: dict[str, list[str]] = {
    "sea salt":          ["table salt", "kosher salt", "rock salt"],
    "table salt":        ["sea salt", "kosher salt"],
    "kosher salt":       ["sea salt", "table salt"],
    "all-purpose flour": ["plain flour", "wheat flour"],
    "plain flour":       ["all-purpose flour", "wheat flour"],
    "cake flour":        ["plain flour", "all-purpose flour"],
    "heavy cream":       ["double cream", "whipping cream"],
    "double cream":      ["heavy cream", "whipping cream"],
    "whipping cream":    ["heavy cream", "double cream"],
    "sour cream":        ["crème fraîche", "greek yogurt"],
    "crème fraîche":     ["sour cream"],
    "greek yogurt":      ["plain yogurt", "sour cream"],
    "basmati rice":      ["jasmine rice", "long-grain rice"],
    "jasmine rice":      ["basmati rice", "long-grain rice"],
    "arborio rice":      ["risotto rice", "short-grain rice"],
    "spring onion":      ["scallion", "green onion", "chive"],
    "scallion":          ["spring onion", "green onion"],
    "green onion":       ["spring onion", "scallion"],
    "zucchini":          ["courgette"],
    "courgette":         ["zucchini"],
    "eggplant":          ["aubergine"],
    "aubergine":         ["eggplant"],
    "cilantro":          ["fresh coriander", "coriander"],
    "coriander":         ["cilantro", "fresh coriander"],
    "bell pepper":       ["capsicum", "sweet pepper"],
    "capsicum":          ["bell pepper", "sweet pepper"],
    "ground beef":       ["minced beef", "minced meat"],
    "minced beef":       ["ground beef"],
    "ground pork":       ["minced pork"],
    "minced pork":       ["ground pork"],
    "sunflower oil":     ["vegetable oil", "canola oil"],
    "vegetable oil":     ["sunflower oil", "canola oil"],
    "canola oil":        ["vegetable oil", "sunflower oil"],
    "pine nuts":         ["walnuts", "cashews"],
    "walnuts":           ["pine nuts", "pecans"],
    "breadcrumbs":       ["panko"],
    "panko":             ["breadcrumbs"],
}


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def clean_ingredient_term(ingredient: str) -> str:
    """Strip quantities, units, and filler adjectives from an ingredient string."""
    cleaned = re.sub(r'^\s*[\d\.\/]+\s*', '', ingredient)

    units = [
        "g", "kg", "ml", "l", "oz", "lb", "cup", "cups",
        "tbsp", "tsp", "tablespoon", "teaspoon", "clove", "cloves",
        "slice", "slices", "piece", "pieces", "can", "cans", "tin", "tins",
        "dash", "pinch", "package", "pack", "box", "stick", "sticks", "bag",
        "handful", "knob", "head", "bunch", "sprig", "sprigs", "bulb", "bulbs",
        "sheet", "sheets", "drop", "drops", "splash",
    ]
    units_pattern = r'\b(?:' + '|'.join(units) + r')\b'
    cleaned = re.sub(units_pattern, '', cleaned, flags=re.IGNORECASE)

    fillers = [
        "of", "ripe", "fresh", "large", "small", "medium", "chopped", "diced",
        "sliced", "melted", "softened", "crushed", "minced", "grated", "peeled",
        "pitted", "seeded", "halved", "quartered", "roughly", "finely", "thinly",
        "thickly", "cooked", "raw", "frozen", "dried", "ground", "whole",
        "lean", "boneless", "skinless", "extra", "garnish",
    ]
    fillers_pattern = r'\b(?:' + '|'.join(fillers) + r')\b'
    cleaned = re.sub(fillers_pattern, '', cleaned, flags=re.IGNORECASE)

    return re.sub(r'\s+', ' ', cleaned).strip()


def classify_ingredient(term: str) -> str:
    """Return the semantic type of a cleaned ingredient term."""
    t = term.lower()
    for ing_type, keywords in INGREDIENT_TYPE_MAP:
        if any(kw in t for kw in keywords):
            return ing_type
    return "other_food"


def calculate_proportion_message(req_text, prod_unit, price):
    if not req_text or not prod_unit or price is None:
        return None

    def parse_amt(text):
        m = re.search(r'([\d\.,]+)\s*([a-zA-Z%]+)', str(text).replace(',', '.'))
        if m:
            return float(m.group(1)), m.group(2).lower()
        return None, None

    req_q, req_u = parse_amt(req_text)
    prod_q, prod_u = parse_amt(prod_unit)
    if not (req_q and prod_q and req_u and prod_u):
        return None


    if req_u in ('kg',): req_q *= 1000; req_u = 'g'
    if req_u in ('l',):  req_q *= 1000; req_u = 'ml'
    if prod_u in ('kg',): prod_q *= 1000; prod_u = 'g'
    if prod_u in ('l',):  prod_q *= 1000; prod_u = 'ml'

    if req_u != prod_u or req_q >= prod_q:
        return None

    prop = req_q / prod_q
    euros = round(price * prop * 100) / 100
    unit_cost = round((price * 100) / prod_q, 2)
    qty_int = int(req_q) if float(req_q).is_integer() else req_q
    return f"Proportion: using {qty_int}{req_u} costs ~€{euros:.2f} ({unit_cost}¢/{req_u})"


def _get_product_price(product):
    cheapest = ProductStore.query.filter_by(
        product_id=product.id, is_available=True
    ).order_by(ProductStore.base_price.asc()).first()
    return float(cheapest.base_price) if cheapest and cheapest.base_price else None


def _get_product_cheapest_store(product):
    cheapest = ProductStore.query.filter_by(
        product_id=product.id, is_available=True
    ).order_by(ProductStore.base_price.asc()).first()
    if not cheapest:
        return None
    store = Store.query.filter_by(store_id=cheapest.store_id).first()
    return store.name if store else cheapest.store_id


def _term_appears_as_whole_word(product_name_lower: str, search_term_lower: str) -> bool:
    """Return True only if search_term appears as a standalone word (not inside a compound)."""
    pattern = r'\b' + re.escape(search_term_lower) + r'\b'
    return bool(re.search(pattern, product_name_lower))


def _is_non_food_product(product_name_lower: str) -> bool:
    """Return True if the product name contains a kitchen-utensil / non-food indicator."""
    for word in NON_FOOD_PRODUCT_WORDS:
        if word in product_name_lower:
            return True
    return False


def _check_category(product, ing_type: str) -> tuple[bool, bool]:
    """
    Single DB fetch for both category checks.

    Returns (is_junk, is_allowed):
    - is_junk    : category is explicitly bad (snacks, beverages, household…)
    - is_allowed : category is appropriate for ing_type per the allowlist
                   (True by default when no category is set or no restriction applies)
    """
    if not product.category_id:
        return False, True  # uncategorized: not junk, no restriction can be applied

    cat = Category.query.get(product.category_id)
    if not cat:
        return False, True

    slug     = (cat.slug or "").lower()
    name_en  = (cat.name_en or "").lower().strip()
    name_de  = (cat.name_de or "").lower().strip()
    combined = f"{slug} {name_en} {name_de}"

    # ── Junk check (blocklist) ─────────────────────────────────────────────
    is_junk = (
        any(root in slug for root in JUNK_SLUG_ROOTS)
        or name_en in JUNK_CATEGORY_NAMES
        or name_de in JUNK_CATEGORY_NAMES
    )

    # ── Allowlist check ────────────────────────────────────────────────────
    allowed_kws = INGREDIENT_TYPE_CATEGORY_ALLOWLIST.get(ing_type)
    if allowed_kws is None:
        is_allowed = True   # no restriction for this ingredient type
    else:
        is_allowed = any(kw in combined for kw in allowed_kws)

    return is_junk, is_allowed


def _is_flavor_descriptor(product_name_lower: str, search_term_lower: str) -> bool:
    """Return True when search_term appears only as a flavor suffix: 'X & Onion'."""
    pattern = r'(?:&|and|und)\s+' + re.escape(search_term_lower) + r'\s*$'
    return bool(re.search(pattern, product_name_lower))


def _is_junk_by_name(product_name_lower: str, search_term_lower: str) -> bool:
    """
    Return True when the product name signals it is not a usable cooking ingredient.
    Checks: global negative keywords, per-ingredient keywords, flavor-suffix pattern.
    Lenient for condiment/seasoning types.
    """
    search_words = set(search_term_lower.split())
    search_first = search_term_lower.split()[0] if search_term_lower else ""

    # Global negative keywords (skip if ingredient IS that kind of product)
    if search_first not in INGREDIENT_IS_DRINK_OR_SNACK:
        for kw in GLOBAL_NEGATIVE_NAME_KEYWORDS:
            if kw in product_name_lower and kw not in search_words:
                return True

    # Per-ingredient keywords
    per_ing = INGREDIENT_NEGATIVE_KEYWORDS.get(search_first, [])
    for ew in per_ing:
        if ew in product_name_lower:
            return True

    # Flavor-suffix ("Cheese & Onion" snack for ingredient "onion")
    if _is_flavor_descriptor(product_name_lower, search_term_lower):
        return True

    return False


# Words that negate or invert the ingredient — always reject regardless of length
_NEGATING_PREFIX_WORDS = frozenset({
    "not", "no", "non", "ohne", "free", "fake", "mock", "vegan", "imitation",
})

def _search_term_is_leading(name_lower: str, search_term_lower: str, ing_type: str) -> bool:
    """
    Return True when the search term is the primary ingredient in the product name.

    For strict types (dairy, protein, produce, grain) we reject:
      - Products where a known food keyword precedes the search term
          ("apple butter tache" → "apple" is food → REJECT)
      - Products where the search term is a hyphen-compound prefix
          ("butter-apfeltasche" → "butter-" is a flavor descriptor → REJECT)
      - Products where a negating word precedes the search term
          ("not milk" → "not" inverts the ingredient → REJECT)
      - Products where a known food/flavor word follows the search term
          ("milk schokolade" → "schokolade" signals flavored variant → REJECT)
    """
    if ing_type not in STRICT_INGREDIENT_TYPES:
        return True

    idx = name_lower.find(search_term_lower)
    if idx < 0:
        return True

    term_end = idx + len(search_term_lower)

    # Reject if immediately followed by a hyphen → compound-word prefix
    # e.g. "butter-apfeltasche": butter is a flavor/descriptor, not the product
    if term_end < len(name_lower) and name_lower[term_end] == '-':
        return False

    # Check prefix words
    prefix_words = name_lower[:idx].split()
    for word in prefix_words:
        if word in _NEGATING_PREFIX_WORDS:
            return False  # "not milk", "no butter" etc.
        if word in _FOOD_PREFIX_WORDS:
            return False  # a food word precedes the ingredient → compound product

    # Check suffix words for flavor descriptors (e.g. "milk schokolade")
    suffix_words = name_lower[term_end:].split()
    _FLAVOR_SUFFIX_WORDS = frozenset({
        "schokolade", "chocolate", "kakao", "vanille", "vanilla",
        "erdbeer", "strawberry", "haselnuss", "hazelnut", "karamel", "caramel",
    })
    for word in suffix_words:
        if word in _FLAVOR_SUFFIX_WORDS:
            return False  # flavored variant of the ingredient, not the plain product

    return True


def _passes_all_filters(product, name_lower: str, search_term_lower: str,
                        ing_type: str, require_whole_word: bool = True) -> bool:
    """Single gate: return True only if this product is an acceptable match."""
    if _is_non_food_product(name_lower):
        return False
    if require_whole_word and not _term_appears_as_whole_word(name_lower, search_term_lower):
        return False
    if not _search_term_is_leading(name_lower, search_term_lower, ing_type):
        return False

    is_junk, is_allowed = _check_category(product, ing_type)

    # Junk categories (snacks, beverages, household…) are blocked except for
    # lenient types where overlap is expected (condiment, seasoning, other_food).
    if is_junk and ing_type not in LENIENT_INGREDIENT_TYPES:
        return False

    # Category allowlist: for typed ingredients (produce, grain, protein, dairy)
    # the product must be in an appropriate category family.
    if not is_allowed:
        return False

    if _is_junk_by_name(name_lower, search_term_lower):
        return False
    return True


# ══════════════════════════════════════════════════════════════════════════════
# GEMINI BATCH VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def _gemini_validate_matches(pairs: list[tuple[str, str]]) -> set[int]:
    """
    Ask Gemini whether each (ingredient, product) pair is a valid cooking match.

    pairs: list of (ingredient_original, product_name)
    Returns a set of 0-based indices that are VALID matches.
    If Gemini is unavailable, returns all indices (no filtering).
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or not pairs:
        return set(range(len(pairs)))

    numbered = "\n".join(
        f"{i+1}. Ingredient: \"{ing}\" → Product: \"{prod}\""
        for i, (ing, prod) in enumerate(pairs)
    )

    prompt = f"""You are a grocery shopping assistant.
For each numbered pair below, decide if the PRODUCT is a realistic grocery item
a home cook would actually buy to fulfill that INGREDIENT in a real recipe.

Rules:
- ACCEPT: the product is the ingredient itself or a direct substitute (e.g. fresh, frozen, canned, powdered form).
- REJECT: the product is a snack, candy, beverage, kitchen tool, cleaning product,
  ready-made meal, pet food, animal food, or any item that uses the ingredient word merely as branding or flavor.
- ALWAYS REJECT any product intended for pets or animals (cat food, dog food, bird food, etc.).

Examples of REJECT:
- Ingredient "mushrooms" → "Sour Mushroom Candy": REJECT (candy)
- Ingredient "sushi rice" → "Bambusmatte für Sushi": REJECT (bamboo rolling mat)
- Ingredient "mirin" → "Mirinda Orange": REJECT (soda)
- Ingredient "garlic" → "Bruschette Garlic Chips": REJECT (snack)

Examples of ACCEPT:
- Ingredient "mushrooms" → "BILLA Bio Champignons": ACCEPT
- Ingredient "garlic" → "Knoblauch 3 Stück": ACCEPT
- Ingredient "soy sauce" → "BILLA Sojasauce": ACCEPT

Now evaluate:
{numbered}

Return ONLY a JSON array of the 1-indexed numbers that are VALID ACCEPTS.
Example: [1, 3, 5]
If none are valid return: []
"""

    url = (
        "https://generativelanguage.googleapis.com/v1beta"
        f"/models/gemini-2.0-flash:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }

    try:
        resp = requests.post(url, json=payload, timeout=12)
        resp.raise_for_status()
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        raw = raw.removeprefix("```json").removesuffix("```").strip()
        valid_1indexed = json.loads(raw)
        if isinstance(valid_1indexed, list):
            return {i - 1 for i in valid_1indexed if isinstance(i, int)}
    except Exception as e:
        print(f"[recipe_matcher] Gemini validation skipped: {e}")

    return set(range(len(pairs)))  # fallback: keep all


# ══════════════════════════════════════════════════════════════════════════════
# MAIN MATCHING FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def _build_match_dict(p, price, store) -> dict:
    unit = p.unit_normalized or ""
    return {
        "id":              str(p.id),
        "productId":       p.fingerprint,
        "name":            p.name_de,
        "name_de":         p.name_de,
        "brand":           p.brand,
        "price":           price,
        "price_val":       price,
        "store":           store,
        "unit":            unit,
        "quantity":        unit,
        "image":           p.default_image_url,
        "defaultImageUrl": p.default_image_url,
    }


def _search_and_filter(search_word: str, ing_type: str,
                       limit: int = 60, require_whole_word: bool = True) -> list:
    """DB search + all filters. Returns scored list of (score_tuple, product)."""
    products = Product.query.filter(
        Product.name_de.ilike(f"%{search_word}%")
    ).order_by(Product.name_de).limit(limit).all()

    scored = []
    for p in products:
        name_lower = (p.name_de or "").lower()
        sw_lower   = search_word.lower()

        if not _passes_all_filters(p, name_lower, sw_lower, ing_type, require_whole_word):
            continue

        price = _get_product_price(p)
        if not price or price <= 0:
            continue

        exact  = 0 if name_lower == sw_lower else 1
        starts = 0 if name_lower.startswith(sw_lower) else 1
        scored.append(((exact, starts, len(name_lower), price), p))

    scored.sort(key=lambda x: x[0])
    return scored


def match_ingredients_to_products(ingredients: list[str]) -> list[dict]:
    """
    Match a list of raw ingredient strings to grocery products.
    Returns one result dict per ingredient with up to 3 matched products.
    """
    results = []
    # Collect (ingredient_original, product_name) pairs for Gemini validation
    gemini_pairs: list[tuple[str, str]] = []
    # Map from pair index → (result_index, match_index)
    pair_to_location: dict[int, tuple[int, int]] = {}

    for raw_ing in ingredients:
        search_term = clean_ingredient_term(raw_ing)
        if not search_term:
            search_term = raw_ing

        ing_type = classify_ingredient(search_term)
        matches: list[dict] = []

        # ── Phase 1: full cleaned term ────────────────────────────────────────
        scored = _search_and_filter(search_term, ing_type)
        for _, p in scored:
            price = _get_product_price(p)
            store = _get_product_cheapest_store(p)
            matches.append(_build_match_dict(p, price, store))
            if len(matches) == 3:
                break

        # ── Phase 2: last word (usually the noun / key food word) ────────────
        # Try this BEFORE the progressive-drop-from-right so that "Red Pepper"
        # searches for "Pepper" rather than first searching for "Red".
        if not matches and ' ' in search_term:
            last_word = search_term.split()[-1]
            if (len(last_word) >= 4
                    and last_word.lower() not in INGREDIENT_MODIFIER_WORDS):
                scored = _search_and_filter(last_word, ing_type)
                for _, p in scored:
                    price = _get_product_price(p)
                    store = _get_product_cheapest_store(p)
                    matches.append(_build_match_dict(p, price, store))
                    if len(matches) == 3:
                        break

        # ── Phase 3: progressively shorter phrases (drop from right) ─────────
        # Skip any shortened term that is a lone modifier word (colour, size…)
        # — searching for "Red" or "Yellow" alone causes nonsense matches.
        if not matches and ' ' in search_term:
            words = search_term.split()
            for drop in range(1, len(words)):
                shorter = ' '.join(words[:-drop])
                if len(shorter) < 3:
                    break
                if shorter.lower() in INGREDIENT_MODIFIER_WORDS:
                    continue  # e.g. "Red" from "Red Pepper" — skip it
                scored = _search_and_filter(shorter, ing_type)
                for _, p in scored:
                    price = _get_product_price(p)
                    store = _get_product_cheapest_store(p)
                    matches.append(_build_match_dict(p, price, store))
                    if len(matches) == 3:
                        break
                if matches:
                    break

        # ── Proportional cost messages ────────────────────────────────────────
        for m in matches:
            prop = calculate_proportion_message(
                raw_ing,
                m.get('unit') or m.get('quantity'),
                m.get('price_val') or m.get('price')
            )
            if prop:
                m['proportional_message'] = prop

        # Register ALL candidates for Gemini validation (not just the best match)
        result_idx = len(results)
        for match_idx, match in enumerate(matches):
            pair_idx = len(gemini_pairs)
            gemini_pairs.append((raw_ing, match["name"]))
            pair_to_location[pair_idx] = (result_idx, match_idx)

        results.append({
            "original_request": raw_ing,
            "search_term":      search_term,
            "ingredient_type":  ing_type,
            "matches":          matches,
        })

    # ── Phase 4: Gemini batch validation ─────────────────────────────────────
    # Gemini now sees every candidate for every ingredient and approves/rejects
    # each one individually — rejected candidates are removed, approved ones kept.
    # The first approved candidate becomes the displayed product.
    if gemini_pairs:
        valid_indices = _gemini_validate_matches(gemini_pairs)
        for pair_idx, (result_idx, match_idx) in pair_to_location.items():
            if pair_idx not in valid_indices:
                result = results[result_idx]
                if match_idx < len(result["matches"]) and result["matches"][match_idx] is not None:
                    rejected_name = result["matches"][match_idx]["name"]
                    print(f"[recipe_matcher] Gemini rejected: '{result['original_request']}' → '{rejected_name}'")
                    result["matches"][match_idx] = None  # mark for removal

        # Strip out rejected matches, preserving order of approved ones
        for result in results:
            result["matches"] = [m for m in result["matches"] if m is not None]

    return results


# ── Quick CLI test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from app import app
    test_ingredients = [
        "300g sushi rice", "1 tbs mirin", "100g shiitake mushrooms",
        "2 cloves minced garlic", "20g ginger", "1 tblsp olive oil",
        "1 chopped onion", "500g minced pork", "1 tsp muscovado sugar",
        "garnish pickle juice",
    ]
    print("Testing semantic ingredient matcher...")
    with app.app_context():
        results = match_ingredients_to_products(test_ingredients)
        for r in results:
            print(f"\n[{r['ingredient_type']:15}] {r['original_request']:35} → search: '{r['search_term']}'")
            if r["matches"]:
                for m in r["matches"]:
                    print(f"    ✓ €{m['price']:.2f}  {m['name']}  ({m['store']})")
            else:
                print("    ✗ no match")
