#!/usr/bin/env python3
"""Expand category taxonomy and backfill deep category paths for products.

This script is idempotent:
- Upserts a multi-level category tree (roots + subcategories).
- Rebuilds path/fullPathNames for taxonomy categories.
- Reclassifies products into deeper leaf categories using keyword scoring.
"""

from __future__ import annotations

import os
import re
import sys
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app  # noqa: F401  # Ensures .env and mongo init side-effects
from utils.db import get_db


ROOTS = [
    {"id": "cat_produce", "name_en": "Produce", "name_de": "Obst & Gemuse"},
    {"id": "cat_pantry", "name_en": "Pantry", "name_de": "Vorrat"},
    {"id": "cat_dairy", "name_en": "Dairy", "name_de": "Molkerei"},
    {"id": "cat_meat", "name_en": "Meat", "name_de": "Fleisch"},
    {"id": "cat_frozen", "name_en": "Frozen", "name_de": "Tiefkuhl"},
    {"id": "cat_bakery", "name_en": "Bakery", "name_de": "Backerei"},
    {"id": "cat_baby-food", "name_en": "Baby food", "name_de": "Babynahrung"},
    {"id": "cat_snacks", "name_en": "Snacks", "name_de": "Snacks"},
    {"id": "cat_fast-food-to-go", "name_en": "Fast Food & To Go", "name_de": "Schnellgerichte & To Go"},
    {"id": "cat_household", "name_en": "Household", "name_de": "Haushalt"},
    {"id": "cat_beverages", "name_en": "Beverages", "name_de": "Getranke"},
]


# A broad taxonomy with many actionable leaves for grouping and recommendations.
TAXONOMY = [
    # Produce
    {"id": "cat_produce_fruits", "parent": "cat_produce", "name_en": "Fruits", "name_de": "Obst", "keywords": ["fruit", "obst", "apple", "banana", "kiwi", "strawberry", "blueberry", "orange", "pear", "grape"]},
    {"id": "cat_produce_vegetables", "parent": "cat_produce", "name_en": "Vegetables", "name_de": "Gemuse", "keywords": ["vegetable", "gemuse", "carrot", "tomato", "pepper", "zucchini", "broccoli", "onion", "salad"]},
    {"id": "cat_produce_herbs", "parent": "cat_produce", "name_en": "Fresh Herbs", "name_de": "Frische Krauter", "keywords": ["herb", "krauter", "basil", "parsley", "mint", "dill", "thyme"]},
    {"id": "cat_produce_salads", "parent": "cat_produce", "name_en": "Salads & Leafy Greens", "name_de": "Salate & Blattgemuse", "keywords": ["salad", "lettuce", "rukola", "spinach", "leafy"]},
    # Pantry
    {"id": "cat_pantry_pasta-rice", "parent": "cat_pantry", "name_en": "Pasta & Rice", "name_de": "Nudeln & Reis", "keywords": ["pasta", "spaghetti", "noodle", "reis", "rice", "risotto"]},
    {"id": "cat_pantry_sauces-condiments", "parent": "cat_pantry", "name_en": "Sauces & Condiments", "name_de": "Saucen & Kondimente", "keywords": ["sauce", "ketchup", "mustard", "mayo", "mayonnaise", "senf", "dressing", "soya", "soy"]},
    {"id": "cat_pantry_oils-vinegars", "parent": "cat_pantry", "name_en": "Oils & Vinegars", "name_de": "Ole & Essig", "keywords": ["oil", "olive", "rapeseed", "vinegar", "essig"]},
    {"id": "cat_pantry_spices", "parent": "cat_pantry", "name_en": "Spices & Seasonings", "name_de": "Gewurze", "keywords": ["spice", "gewurz", "pepper", "salt", "paprika", "curry", "seasoning"]},
    {"id": "cat_pantry_breakfast-spreads", "parent": "cat_pantry", "name_en": "Breakfast & Spreads", "name_de": "Fruhstuck & Aufstriche", "keywords": ["jam", "marmalade", "honey", "nutella", "spread", "peanut butter", "cereal", "muesli", "granola"]},
    {"id": "cat_pantry_baking-needs", "parent": "cat_pantry", "name_en": "Baking Essentials", "name_de": "Backzutaten", "keywords": ["flour", "mehl", "sugar", "zucker", "yeast", "baking", "back", "vanilla"]},
    {"id": "cat_pantry_canned-jarred", "parent": "cat_pantry", "name_en": "Canned & Jarred Goods", "name_de": "Konserven & Glasware", "keywords": ["canned", "can", "tin", "jar", "pickle", "beans", "lentils", "tomato sauce"]},
    # Dairy
    {"id": "cat_dairy_milk", "parent": "cat_dairy", "name_en": "Milk", "name_de": "Milch", "keywords": ["milk", "milch", "whole milk", "skim", "lactose free milk"]},
    {"id": "cat_dairy_yogurt", "parent": "cat_dairy", "name_en": "Yogurt", "name_de": "Joghurt", "keywords": ["yogurt", "joghurt", "greek yogurt", "protein pudding", "skyr"]},
    {"id": "cat_dairy_cheese", "parent": "cat_dairy", "name_en": "Cheese", "name_de": "Kase", "keywords": ["cheese", "kase", "mozzarella", "cheddar", "gouda", "parmesan"]},
    {"id": "cat_dairy_butter-cream", "parent": "cat_dairy", "name_en": "Butter & Cream", "name_de": "Butter & Sahne", "keywords": ["butter", "cream", "sahne", "creme fraiche", "mascarpone"]},
    {"id": "cat_dairy_eggs", "parent": "cat_dairy", "name_en": "Eggs", "name_de": "Eier", "keywords": ["egg", "eggs", "eier"]},
    # Meat
    {"id": "cat_meat_fresh-meat", "parent": "cat_meat", "name_en": "Fresh Meat", "name_de": "Frischfleisch", "keywords": ["beef", "pork", "veal", "lamb", "fresh meat", "fleisch"]},
    {"id": "cat_meat_poultry", "parent": "cat_meat", "name_en": "Poultry", "name_de": "Geflugel", "keywords": ["chicken", "turkey", "poultry", "geflugel"]},
    {"id": "cat_meat_sausages-coldcuts", "parent": "cat_meat", "name_en": "Sausages & Cold Cuts", "name_de": "Wurst & Aufschnitt", "keywords": ["sausage", "salami", "ham", "wurst", "aufschnitt", "cold cut"]},
    {"id": "cat_meat_seafood", "parent": "cat_meat", "name_en": "Seafood", "name_de": "Fisch & Meeresfruchte", "keywords": ["fish", "salmon", "tuna", "shrimp", "seafood", "fisch"]},
    # Frozen
    {"id": "cat_frozen_pizza", "parent": "cat_frozen", "name_en": "Frozen Pizza", "name_de": "Tiefkuhlpizza", "keywords": ["frozen pizza", "pizza", "margherita", "tiefkuhlpizza"]},
    {"id": "cat_frozen_vegetables-fruits", "parent": "cat_frozen", "name_en": "Frozen Vegetables & Fruits", "name_de": "Tiefkuhlgemuse & Obst", "keywords": ["frozen vegetable", "frozen fruit", "tiefkuhlgemuse", "berries frozen"]},
    {"id": "cat_frozen_ready-meals", "parent": "cat_frozen", "name_en": "Frozen Ready Meals", "name_de": "Tiefkuhl Fertiggerichte", "keywords": ["frozen meal", "ready meal", "lasagna", "nuggets", "strudel frozen"]},
    {"id": "cat_frozen_ice-cream", "parent": "cat_frozen", "name_en": "Ice Cream & Desserts", "name_de": "Eis & Desserts", "keywords": ["ice cream", "gelato", "sorbet", "eis", "frozen dessert"]},
    # Bakery
    {"id": "cat_bakery_bread", "parent": "cat_bakery", "name_en": "Bread", "name_de": "Brot", "keywords": ["bread", "brot", "sourdough", "toast", "loaf"]},
    {"id": "cat_bakery_rolls-buns", "parent": "cat_bakery", "name_en": "Rolls & Buns", "name_de": "Semmeln & Weckerl", "keywords": ["roll", "bun", "semmel", "weckerl", "bagel"]},
    {"id": "cat_bakery_pastries", "parent": "cat_bakery", "name_en": "Pastries", "name_de": "Feingeback", "keywords": ["croissant", "pastry", "danish", "strudel", "pain au chocolat"]},
    {"id": "cat_bakery_cakes-desserts", "parent": "cat_bakery", "name_en": "Cakes & Desserts", "name_de": "Kuchen & Desserts", "keywords": ["cake", "kuchen", "muffin", "donut", "dessert"]},
    # Baby food
    {"id": "cat_baby-food_formula", "parent": "cat_baby-food", "name_en": "Infant Formula", "name_de": "Sauglingnahrung", "keywords": ["formula", "pre milk", "infant milk", "baby milk"]},
    {"id": "cat_baby-food_purees", "parent": "cat_baby-food", "name_en": "Purees & Meals", "name_de": "Brei & Mahlzeiten", "keywords": ["puree", "baby puree", "baby meal", "baby food", "brei"]},
    {"id": "cat_baby-food_snacks", "parent": "cat_baby-food", "name_en": "Baby Snacks", "name_de": "Baby Snacks", "keywords": ["baby snack", "teething", "baby biscuit", "baby bar"]},
    {"id": "cat_baby-food_drinks", "parent": "cat_baby-food", "name_en": "Baby Drinks", "name_de": "Baby Getranke", "keywords": ["baby water", "baby tea", "baby juice", "mineralwasser baby"]},
    # Snacks
    {"id": "cat_snacks_chips", "parent": "cat_snacks", "name_en": "Chips", "name_de": "Chips", "keywords": ["chips", "crisps", "pringles", "nacho"]},
    {"id": "cat_snacks_nuts-seeds", "parent": "cat_snacks", "name_en": "Nuts & Seeds", "name_de": "Nusse & Kerne", "keywords": ["nuts", "almond", "cashew", "hazelnut", "seeds", "trail mix"]},
    {"id": "cat_snacks_protein-bars", "parent": "cat_snacks", "name_en": "Protein & Energy Bars", "name_de": "Proteinriegel & Energieriegel", "keywords": ["protein bar", "energy bar", "cereal bar", "riegel"]},
    {"id": "cat_snacks_crackers", "parent": "cat_snacks", "name_en": "Crackers & Savory Snacks", "name_de": "Cracker & Salzgeback", "keywords": ["cracker", "pretzel", "salt sticks", "bruschetta", "snack mix"]},
    {"id": "cat_snacks_sweets", "parent": "cat_snacks", "name_en": "Sweets & Chocolate", "name_de": "Susswaren & Schokolade", "keywords": ["chocolate", "candy", "sweets", "bonbon", "gummy", "cookie", "biscuit"]},
    # Fast Food & To Go
    {"id": "cat_fast-food-to-go_wraps-sandwiches", "parent": "cat_fast-food-to-go", "name_en": "Wraps & Sandwiches", "name_de": "Wraps & Sandwiches", "keywords": ["wrap", "sandwich", "baguette", "panini", "toastie"]},
    {"id": "cat_fast-food-to-go_salads-bowls", "parent": "cat_fast-food-to-go", "name_en": "Salads & Bowls", "name_de": "Salate & Bowls", "keywords": ["caesar", "bowl", "ready salad", "meal salad"]},
    {"id": "cat_fast-food-to-go_ready-snacks", "parent": "cat_fast-food-to-go", "name_en": "Ready Snacks", "name_de": "Fertige Snacks", "keywords": ["ready snack", "to go", "snack box", "on the go"]},
    {"id": "cat_fast-food-to-go_hot-meals", "parent": "cat_fast-food-to-go", "name_en": "Ready Hot Meals", "name_de": "Fertige Warmgerichte", "keywords": ["ready meal", "microwave", "hot meal", "curry box", "lasagne to go"]},
    # Household
    {"id": "cat_household_cleaning", "parent": "cat_household", "name_en": "Cleaning Supplies", "name_de": "Reinigungsmittel", "keywords": ["cleaner", "detergent", "spulmittel", "dish soap", "surface cleaner", "bleach"]},
    {"id": "cat_household_paper-hygiene", "parent": "cat_household", "name_en": "Paper & Hygiene", "name_de": "Papier & Hygiene", "keywords": ["toilet paper", "kitchen towel", "paper towel", "tissue", "napkin"]},
    {"id": "cat_household_laundry", "parent": "cat_household", "name_en": "Laundry", "name_de": "Waschmittel", "keywords": ["laundry", "washing powder", "fabric softener", "wash tabs"]},
    {"id": "cat_household_storage-foil", "parent": "cat_household", "name_en": "Storage & Foil", "name_de": "Aufbewahrung & Folien", "keywords": ["foil", "cling film", "baking paper", "freezer bag", "storage bag"]},
    {"id": "cat_household_pet-care", "parent": "cat_household", "name_en": "Pet Care", "name_de": "Tierbedarf", "keywords": ["cat food", "dog food", "pet", "litter", "tier"]},
    # Beverages
    {"id": "cat_beverages_water", "parent": "cat_beverages", "name_en": "Water", "name_de": "Wasser", "keywords": ["water", "mineralwasser", "sparkling water", "still water"]},
    {"id": "cat_beverages_soft-drinks", "parent": "cat_beverages", "name_en": "Soft Drinks", "name_de": "Erfrischungsgetranke", "keywords": ["cola", "fanta", "sprite", "soft drink", "soda", "limonade"]},
    {"id": "cat_beverages_juice-nectar", "parent": "cat_beverages", "name_en": "Juice & Nectars", "name_de": "Safte & Nektare", "keywords": ["juice", "saft", "nectar", "orange juice", "apple juice"]},
    {"id": "cat_beverages_coffee", "parent": "cat_beverages", "name_en": "Coffee", "name_de": "Kaffee", "keywords": ["coffee", "kaffee", "espresso", "nescafe", "cappuccino"]},
    {"id": "cat_beverages_tea", "parent": "cat_beverages", "name_en": "Tea", "name_de": "Tee", "keywords": ["tea", "tee", "herbal tea", "green tea", "iced tea"]},
    {"id": "cat_beverages_energy-sports", "parent": "cat_beverages", "name_en": "Energy & Sports Drinks", "name_de": "Energy & Sportgetranke", "keywords": ["energy drink", "sports drink", "isotonic", "red bull"]},
    {"id": "cat_beverages_alcohol", "parent": "cat_beverages", "name_en": "Alcoholic Drinks", "name_de": "Alkoholische Getranke", "keywords": ["beer", "wine", "vodka", "gin", "whiskey", "sekt"]},
]


DEFAULT_LEAF_BY_ROOT = {
    "cat_produce": "cat_produce_fruits",
    "cat_pantry": "cat_pantry_pasta-rice",
    "cat_dairy": "cat_dairy_milk",
    "cat_meat": "cat_meat_fresh-meat",
    "cat_frozen": "cat_frozen_ready-meals",
    "cat_bakery": "cat_bakery_bread",
    "cat_baby-food": "cat_baby-food_purees",
    "cat_snacks": "cat_snacks_crackers",
    "cat_fast-food-to-go": "cat_fast-food-to-go_ready-snacks",
    "cat_household": "cat_household_cleaning",
    "cat_beverages": "cat_beverages_soft-drinks",
}


def now_utc():
    return datetime.utcnow()


def tokenize(text: str) -> str:
    txt = (text or "").lower()
    txt = re.sub(r"[^a-z0-9\s\-&]", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def _build_lookup() -> Dict[str, dict]:
    lookup = {}
    for root in ROOTS:
        lookup[root["id"]] = {
            "id": root["id"],
            "parent": None,
            "name_en": root["name_en"],
            "name_de": root["name_de"],
            "slug": root["id"].replace("cat_", ""),
            "keywords": [],
        }
    for row in TAXONOMY:
        lookup[row["id"]] = {
            "id": row["id"],
            "parent": row["parent"],
            "name_en": row["name_en"],
            "name_de": row["name_de"],
            "slug": row["id"].replace("cat_", ""),
            "keywords": [k.lower() for k in row.get("keywords", [])],
        }
    return lookup


def _build_path(lookup: Dict[str, dict], cid: str) -> List[str]:
    out = []
    seen = set()
    cur = cid
    while cur and cur not in seen:
        seen.add(cur)
        out.insert(0, cur)
        cur = lookup.get(cur, {}).get("parent")
    return out


def upsert_categories(db, lookup: Dict[str, dict]) -> int:
    changed = 0
    for cid, node in lookup.items():
        path = _build_path(lookup, cid)
        full = []
        for pid in path:
            pnode = lookup.get(pid, {})
            full.append({
                "categoryId": pid,
                "name_en": pnode.get("name_en") or "",
                "name_de": pnode.get("name_de") or "",
                "slug": pnode.get("slug") or pid.replace("cat_", ""),
            })

        res = db.categories.update_one(
            {"categoryId": cid},
            {
                "$set": {
                    "categoryId": cid,
                    "name_en": node.get("name_en"),
                    "name_de": node.get("name_de"),
                    "slug": node.get("slug"),
                    "parentId": node.get("parent"),
                    "path": path,
                    "fullPathNames": full,
                    "updatedAt": now_utc(),
                },
                "$setOnInsert": {
                    "createdAt": now_utc(),
                },
            },
            upsert=True,
        )
        changed += (1 if res.upserted_id is not None else 0)
    return changed


def _root_from_product(product: dict) -> Optional[str]:
    cid = product.get("categoryId")
    path = product.get("categoryPath") or []
    if isinstance(path, list) and path:
        first = str(path[0])
        if first.startswith("cat_"):
            return first
    if isinstance(cid, str) and cid.startswith("cat_"):
        parts = cid.split("_")
        if len(parts) >= 2:
            # Keep legacy roots as-is if already one of known roots
            if cid in DEFAULT_LEAF_BY_ROOT:
                return cid
            # Try extracting root from prefixed leaves, e.g. cat_dairy_yogurt
            maybe_root = "_".join(parts[:2])
            if maybe_root in DEFAULT_LEAF_BY_ROOT:
                return maybe_root
            # Handle roots with hyphens (cat_fast-food-to-go)
            if cid.startswith("cat_fast-food-to-go"):
                return "cat_fast-food-to-go"
            if cid.startswith("cat_baby-food"):
                return "cat_baby-food"
    return None


def classify_product(product: dict, leaves: List[dict], leaf_paths: Dict[str, List[str]]) -> str:
    text = " ".join(
        [
            str(product.get("name_en") or ""),
            str(product.get("name_de") or ""),
            str(product.get("description_en") or ""),
            str(product.get("description_de") or ""),
            str(product.get("category") or ""),
            " ".join([str(x) for x in (product.get("labels") or [])]),
        ]
    )
    text = tokenize(text)

    product_root = _root_from_product(product)

    best_id = None
    best_score = -1
    for leaf in leaves:
        score = 0
        leaf_id = leaf["id"]
        path = leaf_paths.get(leaf_id, [])
        leaf_root = path[0] if path else None

        if product_root and leaf_root == product_root:
            score += 3

        for kw in leaf.get("keywords", []):
            if not kw:
                continue
            kw_norm = tokenize(kw)
            if not kw_norm:
                continue
            if kw_norm in text:
                # longer keywords are more discriminative
                score += 2 + min(4, len(kw_norm.split()))

        # mild boost if leaf label words appear in product text
        label_hint = tokenize(leaf.get("name_en", ""))
        if label_hint and label_hint in text:
            score += 2

        if score > best_score:
            best_score = score
            best_id = leaf_id

    if best_id:
        return best_id

    if product_root and product_root in DEFAULT_LEAF_BY_ROOT:
        return DEFAULT_LEAF_BY_ROOT[product_root]

    return "cat_pantry_pasta-rice"


def backfill_product_paths(db, lookup: Dict[str, dict]) -> dict:
    leaves = [lookup[cid] for cid in lookup if lookup[cid].get("keywords")]
    leaf_paths = {leaf["id"]: _build_path(lookup, leaf["id"]) for leaf in leaves}

    updated = 0
    assigned_counts = Counter()

    cursor = db.products.find({"productId": {"$exists": True}}, {"_id": 1, "productId": 1, "categoryId": 1, "categoryPath": 1, "name_en": 1, "name_de": 1, "description_en": 1, "description_de": 1, "labels": 1, "category": 1})
    for row in cursor:
        leaf_id = classify_product(row, leaves, leaf_paths)
        path = leaf_paths.get(leaf_id, [leaf_id])

        res = db.products.update_one(
            {"_id": row["_id"]},
            {
                "$set": {
                    "categoryId": leaf_id,
                    "categoryPath": path,
                    "updatedAt": now_utc(),
                }
            },
        )
        if res.modified_count > 0:
            updated += 1
        assigned_counts[leaf_id] += 1

    return {"updated_products": updated, "assigned_counts": assigned_counts}


def main() -> None:
    db = get_db()
    if db is None:
        raise RuntimeError("Database unavailable")

    lookup = _build_lookup()

    categories_before = db.categories.count_documents({})
    products_before = db.products.count_documents({"productId": {"$exists": True}})

    inserted = upsert_categories(db, lookup)
    result = backfill_product_paths(db, lookup)

    db.schema_migrations.update_one(
        {"key": "category_taxonomy_expansion_v1"},
        {
            "$set": {
                "key": "category_taxonomy_expansion_v1",
                "appliedAt": now_utc(),
                "categoriesBefore": categories_before,
                "categoriesAfter": db.categories.count_documents({}),
                "productsCount": products_before,
                "productsUpdated": result["updated_products"],
                "notes": "Expanded taxonomy and backfilled deep category paths",
            }
        },
        upsert=True,
    )

    print("Category taxonomy expansion complete")
    print("categories_before:", categories_before)
    print("categories_after:", db.categories.count_documents({}))
    print("products_total:", products_before)
    print("products_updated:", result["updated_products"])
    print("top_assigned_categories:")
    for cid, count in result["assigned_counts"].most_common(20):
        print(f"  {cid}: {count}")


if __name__ == "__main__":
    main()
