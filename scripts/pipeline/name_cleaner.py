#!/usr/bin/env python3
"""
Step 1 – Professional Product Name Cleaning
══════════════════════════════════════════

Produces clean, professional, descriptive names suitable for an Austrian
grocery catalog. Handles:
  - Store prefix removal (BILLA, SPAR, HOFER)
  - Brand extraction into separate field
  - English-to-German term translation
  - Unit/size normalization
  - Proper formatting: "Brand Product Description Size"

Usage:
  python scripts/pipeline/name_cleaner.py --dry-run --limit 30
  python scripts/pipeline/name_cleaner.py              # live
"""

import os
import re
import sys
from pathlib import Path

_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv
load_dotenv(_project_root / ".env", override=True)

# ───────────────────────────────────────────────────────────────────────
# STORE PREFIX REMOVAL
# ───────────────────────────────────────────────────────────────────────

_STORE_PREFIX_RE = re.compile(
    r"^(?:billa|spar|hofer|lidl|penny|dm|mpreis|interspar|eurospar|unimarkt|zelger|konsum)"
    r"(?:\s*(?:plus|bio|natur\s*pur|qualitätsmarke|qualitatsmarke))?"
    r"\s*",
    re.IGNORECASE,
)

# ───────────────────────────────────────────────────────────────────────
# BRAND DICTIONARY (Austrian grocery brands)
# ───────────────────────────────────────────────────────────────────────

BRANDS = [
    "Milfina", "Milbona", "Arla", "Zott", "Bergland", "Nestle",
    "Maggi", "Knorr", "Pfanni", "Dr. Oetker", "Iglo", "Frosta",
    "Darbo", "Stauds", "Manner", "Julius Meinl", "Alma",
    "Ottakringer", "Gosser", "Stiegl", "Zipfer",
    "Almdudler", "Red Bull", "Voslauer", "Romerquelle",
    "Prebl", "Eggenberger", "Kotanyi", "Wiberg", "Mark",
    "Ja! Naturlich", "Natur pur", "Clever", "S-Budget",
    "Zuruck zu Ursprung", "Billa Bio", "Spar Bio",
    "Gut & Gunstig", "K-Classic", "Penny Bio",
    "Lindt", "Milka", "Suchard", "Toblerone", "Ritter Sport",
    "Haribo", "Chio", "Coca-Cola", "Pepsi", "Fanta", "Sprite",
    "Schweppes", "Alpro", "Berchtesgadener Land", "Schardinger",
    "Tirol Milch", "Karntnermilch", "Puck", "Reeses",
    "Pringles", "Nutella", "Nutella", "Philadelphia",
    "Hipp", "Aqua", "BI HOME", "Maretti",
    "Vivis", "Billa", "Spar", "Hofer",
]

# ───────────────────────────────────────────────────────────────────────
# ENGLISH → GERMAN TRANSLATIONS (only for common grocery terms where
# translation improves clarity – keep English brand names & product names)
# ───────────────────────────────────────────────────────────────────────

_EN_DE = {
    # Dairy – common terms where German is expected
    "milk": "Milch", "butter": "Butter", "cheese": "Kase",
    "yogurt": "Joghurt", "cream": "Sahne", "eggs": "Eier",
    "egg": "Ei", "quark": "Topfen",
    "sour cream": "Schmand", "whipped cream": "Schlagsahne",
    # Produce – only where German is clearly expected
    "banana": "Banane", "bananas": "Bananen",
    "apple": "Apfel", "apples": "Apfel",
    "oranges": "Orangen", "lemon": "Zitrone", "lemons": "Zitronen",
    "strawberry": "Erdbeere", "strawberries": "Erdbeeren",
    "blueberry": "Heidelbeere", "blueberries": "Heidelbeeren",
    "tomato": "Tomate", "tomatoes": "Tomaten",
    "cucumber": "Gurke", "carrot": "Karotte", "carrots": "Karotten",
    "potato": "Kartoffel", "potatoes": "Kartoffel",
    "onion": "Zwiebel", "onions": "Zwiebel",
    "mushroom": "Champignon", "mushrooms": "Champignons",
    "fruit": "Obst", "vegetable": "Gemuse", "vegetables": "Gemuse",
    # Bakery
    "bread": "Brot", "roll": "Semmel", "rolls": "Semmel",
    # Pantry
    "pasta": "Pasta", "rice": "Reis", "oil": "Ol",
    "vinegar": "Essig", "salt": "Salz", "pepper": "Pfeffer",
    "sugar": "Zucker", "flour": "Mehl",
    "sauce": "Sauce", "honey": "Honig", "jam": "Marmelade",
    "peanut butter": "Erdnussbutter",
    # Beverages
    "water": "Wasser", "juice": "Saft", "tea": "Tee",
    "coffee": "Kaffee", "beer": "Bier", "wine": "Wein",
    "iced tea": "Eistee", "sparkling water": "Mineralwasser",
    # Household
    "toilet paper": "Toilettenpapier", "paper towel": "Kuchenrolle",
    "detergent": "Waschmittel", "soap": "Seife",
    "diaper": "Windel", "diapers": "Windeln",
    # Snacks
    "chocolate": "Schokolade",
    "chips": "Chips", "cookies": "Kekse", "cookie": "Keks",
    "bar": "Riegel", "protein bar": "Proteinriegel",
    # Packaging descriptors
    "pack": "Packung", "box": "Schachtel", "bottle": "Flasche",
    "can": "Dose", "jar": "Glas", "bag": "Beutel",
    "piece": "Stk", "pieces": "Stk", "pc": "Stk",
    "dozen": "10 Stk",
}

# ───────────────────────────────────────────────────────────────────────
# UNIT PATTERN MATCHING
# ───────────────────────────────────────────────────────────────────────

_UNIT_RE = re.compile(
    r"(\d+[.,]?\d*)\s*"
    r"(l|liter|ml|cl|dl|g|kg|milliliter|gramm|kilogramm|stuck|stk|st|pk|pack|dose|beut|glas|flasch)"
    r"\b",
    re.IGNORECASE,
)

_UNIT_MAP = {
    "l": "Liter", "liter": "Liter", "ltr": "Liter",
    "ml": "ml", "milliliter": "ml",
    "cl": "cl", "dl": "dl",
    "g": "g", "gramm": "g", "gram": "g",
    "kg": "kg", "kilogramm": "kg",
    "st": "Stk", "stk": "Stk", "stuck": "Stk",
    "pk": "Packung", "pack": "Packung",
    "dose": "Dose", "beut": "Beutel", "beutel": "Beutel",
    "glas": "Glas", "flasch": "Flasche",
}

# ───────────────────────────────────────────────────────────────────────
# CLEANUP PATTERNS
# ───────────────────────────────────────────────────────────────────────

_RE_JUNK = re.compile(r"[°*†‡~]+")
_RE_MULTI_SPACE = re.compile(r"\s+")
_RE_TRAILING_DASH = re.compile(r"[-–—]+$")
_RE_LEADING_DASH = re.compile(r"^[-–—&*]+\s*")
_RE_DOUBLE_PUNCT = re.compile(r"([.,;:])\1+")
_RE_TRAILING_SIZE = re.compile(r"\s+\d+[.,]?\d*\s*(g|ml|l|kg|L)\b", re.IGNORECASE)

# ───────────────────────────────────────────────────────────────────────
# CORE FUNCTIONS
# ───────────────────────────────────────────────────────────────────────

def strip_store_prefix(name: str) -> str:
    # Apply twice to handle chained prefixes like "SPAR mPreis ..."
    result = _STORE_PREFIX_RE.sub("", name).strip()
    result = _STORE_PREFIX_RE.sub("", result).strip()
    return result


def extract_brand(name: str) -> tuple[str, str | None]:
    for brand in sorted(BRANDS, key=len, reverse=True):
        pattern = re.compile(r"(?i)(?:^|\s)" + re.escape(brand) + r"(?:\s|$)")
        if pattern.search(name):
            clean = pattern.sub(" ", name).strip()
            clean = _RE_MULTI_SPACE.sub(" ", clean).strip()
            if clean:
                return clean, brand
    return name, None


def translate_to_german(name: str) -> str:
    """Translate common English grocery terms to German."""
    lower = name.lower()

    # Try multi-word translations first (longest first)
    sorted_terms = sorted(_EN_DE.keys(), key=len, reverse=True)
    for term in sorted_terms:
        pattern = re.compile(r"(?i)\b" + re.escape(term) + r"\b")
        if pattern.search(lower):
            name = pattern.sub(_EN_DE[term], name)
            lower = name.lower()

    return name


def normalize_size(name: str) -> tuple[str, str]:
    """
    Extract size from name and return (cleaned_name, size_str).
    E.g. "Extra Virgin Olive Oil 500ml" → ("Extra Virgin Olive Oil", "500 ml")
    """
    sizes_found = []

    def _replace(m):
        val = m.group(1).replace(",", ".")
        unit = m.group(2).lower()
        normalised = _UNIT_MAP.get(unit, unit)
        sizes_found.append(f"{val} {normalised}")
        return ""

    cleaned = _UNIT_RE.sub(_replace, name).strip()
    cleaned = _RE_MULTI_SPACE.sub(" ", cleaned).strip()

    # Remove trailing standalone numbers that might be prices
    cleaned = re.sub(r"\s+\d+\.\d{2}$", "", cleaned)

    size_str = ", ".join(sizes_found) if sizes_found else ""
    return cleaned, size_str


def clean_name(raw: str) -> dict:
    """
    Full name cleaning pipeline. Returns:
      {
        "original": str,
        "name_de": str,       # Display-ready, professional
        "name_en": str,       # Same as name_de (heissepreise names are clean)
        "brand": str | None,  # Extracted brand
        "size": str,          # Normalized size (e.g. "500 ml")
        "quantity": float | None,
        "unit_raw": str | None,
      }
    """
    original = raw.strip()
    name = original

    # 1. Strip store prefix
    name = strip_store_prefix(name)

    # 2. Clean junk characters
    name = _RE_JUNK.sub("", name)
    name = _RE_LEADING_DASH.sub("", name)
    name = _RE_TRAILING_DASH.sub("", name)
    name = _RE_DOUBLE_PUNCT.sub(r"\1", name)

    # 3. Extract brand
    name, brand = extract_brand(name)

    # 4. Extract size from name (e.g. "Extra Virgin Olive Oil 500ml" → size="500 ml")
    name, size = normalize_size(name)

    # 5. Clean whitespace
    name = _RE_MULTI_SPACE.sub(" ", name).strip()

    # 6. Title case (keep known proper nouns intact)
    # German prepositions stay lowercase
    DE_LOWER_WORDS = {"de", "la", "di", "e", "in", "zu", "auf", "mit", "von", "und", "oder", "fur", "im", "am", "zum", "zur", "di", "del", "van"}
    words = name.split()
    title_words = []
    for w in words:
        if w.lower() in DE_LOWER_WORDS:
            title_words.append(w.lower())
        else:
            if len(w) > 1:
                title_words.append(w[0].upper() + w[1:])
            else:
                title_words.append(w.upper())
    name_de = " ".join(title_words)

    # Parse quantity and unit from size
    quantity = None
    unit_raw = None
    if size:
        parts = size.split()
        if parts:
            try:
                quantity = float(parts[0])
            except:
                pass
            if len(parts) > 1:
                unit_raw = parts[1]

    return {
        "original": original,
        "name_de": name_de,
        "name_en": name_de,
        "brand": brand,
        "size": size,
        "quantity": quantity,
        "unit_raw": unit_raw,
    }


# ───────────────────────────────────────────────────────────────────────
# DATABASE OPERATIONS
# ───────────────────────────────────────────────────────────────────────

def get_db():
    import certifi
    from pymongo import MongoClient
    client = MongoClient(
        os.environ["MONGO_URI"],
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=30000,
    )
    return client[os.environ.get("DATABASE_NAME", "smart_grocery")]


def apply_clean_names(db=None, dry_run=False, limit=0):
    """Apply name cleaning to all products."""
    if db is None:
        db = get_db()

    cursor = db.products.find({})
    if limit > 0:
        cursor = cursor.limit(limit)

    docs = list(cursor)
    print(f"Found {len(docs):,} products to clean")

    if dry_run:
        print("\n--- DRY RUN SAMPLES ---")
        for i, doc in enumerate(docs[:30]):
            name = doc.get("name_de") or doc.get("name_en") or doc.get("name", "")
            result = clean_name(name)
            print(f"  [{i+1}] Before: {result['original']}")
            print(f"       After:  {result['name_de']}")
            print(f"       Brand:  {result['brand'] or '(none)'}")
            print(f"       Size:   {result['size'] or '(none)'}")
            print()
        return {"dry_run": True, "total": len(docs)}

    from pymongo import UpdateOne
    operations = []

    for doc in docs:
        name = doc.get("name_de") or doc.get("name_en") or doc.get("name", "")
        result = clean_name(name)

        updates = {
            "name_de": result["name_de"],
            "name_en": result["name_en"],
            "updatedAt": __import__("datetime").datetime.utcnow(),
        }
        if result["brand"]:
            updates["brand"] = result["brand"]
        if result["size"]:
            updates["sizeDisplay"] = result["size"]
        if result["quantity"] is not None:
            updates["quantity"] = result["quantity"]
        if result["unit_raw"]:
            updates["unit_raw"] = result["unit_raw"]

        operations.append(UpdateOne({"_id": doc["_id"]}, {"$set": updates}))

        if len(operations) % 2000 == 0:
            done = len(operations)
            print(f"  Prepared: {done:,}/{len(docs):,}")

    # Execute
    print(f"Executing {len(operations):,} updates...")
    batch_size = 2000
    for i in range(0, len(operations), batch_size):
        db.products.bulk_write(operations[i:i + batch_size], ordered=False)
        done = min(i + batch_size, len(operations))
        print(f"  Updated: {done:,}/{len(operations):,}")

    print(f"Done: {len(operations):,} products cleaned")
    return {"updated": len(operations), "total": len(docs)}


# ───────────────────────────────────────────────────────────────────────
# CLI
# ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Clean product names")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    result = apply_clean_names(dry_run=args.dry_run, limit=args.limit)
    print(f"\nResult: {result}")
