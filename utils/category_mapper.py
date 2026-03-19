"""Category normalization helpers.

This module provides a richer keyword mapper for assigning both a leaf
category and its path under the production taxonomy.
"""

from __future__ import annotations

import re


class CategoryMapper:
    def __init__(self):
        # Leaf -> (root, keywords)
        self.leaf_rules = {
            "cat_produce_fruits": ("cat_produce", ["fruit", "obst", "apple", "banana", "kiwi", "berry", "orange", "pear"]),
            "cat_produce_vegetables": ("cat_produce", ["vegetable", "gemuse", "carrot", "tomato", "broccoli", "pepper", "onion"]),
            "cat_dairy_milk": ("cat_dairy", ["milk", "milch", "lactose", "whole milk", "skim"]),
            "cat_dairy_yogurt": ("cat_dairy", ["yogurt", "joghurt", "skyr", "pudding"]),
            "cat_dairy_cheese": ("cat_dairy", ["cheese", "kase", "mozzarella", "gouda", "cheddar", "parmesan"]),
            "cat_dairy_eggs": ("cat_dairy", ["egg", "eier"]),
            "cat_meat_poultry": ("cat_meat", ["chicken", "turkey", "poultry", "geflugel"]),
            "cat_meat_sausages-coldcuts": ("cat_meat", ["salami", "ham", "sausage", "wurst", "cold cut"]),
            "cat_meat_seafood": ("cat_meat", ["fish", "fisch", "salmon", "tuna", "shrimp", "seafood"]),
            "cat_meat_fresh-meat": ("cat_meat", ["beef", "pork", "lamb", "veal", "fleisch"]),
            "cat_frozen_pizza": ("cat_frozen", ["frozen pizza", "pizza", "margherita"]),
            "cat_frozen_ice-cream": ("cat_frozen", ["ice cream", "gelato", "sorbet", "eis"]),
            "cat_frozen_ready-meals": ("cat_frozen", ["frozen", "ready meal", "lasagna", "nuggets"]),
            "cat_bakery_bread": ("cat_bakery", ["bread", "brot", "loaf", "toast"]),
            "cat_bakery_rolls-buns": ("cat_bakery", ["roll", "bun", "semmel", "weckerl", "bagel"]),
            "cat_bakery_pastries": ("cat_bakery", ["croissant", "pastry", "strudel", "danish"]),
            "cat_baby-food_purees": ("cat_baby-food", ["baby puree", "baby food", "puree", "brei"]),
            "cat_baby-food_formula": ("cat_baby-food", ["formula", "infant milk", "pre milk"]),
            "cat_snacks_chips": ("cat_snacks", ["chips", "crisps", "pringles", "nacho"]),
            "cat_snacks_protein-bars": ("cat_snacks", ["protein bar", "energy bar", "riegel"]),
            "cat_snacks_sweets": ("cat_snacks", ["chocolate", "candy", "sweets", "gummy", "cookie", "biscuit"]),
            "cat_snacks_crackers": ("cat_snacks", ["cracker", "pretzel", "bruschetta", "snack"]),
            "cat_fast-food-to-go_wraps-sandwiches": ("cat_fast-food-to-go", ["wrap", "sandwich", "baguette", "panini"]),
            "cat_fast-food-to-go_salads-bowls": ("cat_fast-food-to-go", ["salad bowl", "caesar", "bowl"]),
            "cat_household_cleaning": ("cat_household", ["cleaner", "detergent", "dish soap", "bleach"]),
            "cat_household_paper-hygiene": ("cat_household", ["toilet paper", "tissue", "paper towel", "napkin"]),
            "cat_household_laundry": ("cat_household", ["laundry", "washing powder", "fabric softener"]),
            "cat_beverages_water": ("cat_beverages", ["water", "mineralwasser", "sparkling water"]),
            "cat_beverages_soft-drinks": ("cat_beverages", ["cola", "soft drink", "soda", "limonade"]),
            "cat_beverages_juice-nectar": ("cat_beverages", ["juice", "saft", "nectar"]),
            "cat_beverages_coffee": ("cat_beverages", ["coffee", "kaffee", "espresso", "nescafe"]),
            "cat_beverages_tea": ("cat_beverages", ["tea", "tee", "iced tea"]),
        }

        self.root_fallback = {
            "cat_produce": "cat_produce_fruits",
            "cat_pantry": "cat_pantry_sauces-condiments",
            "cat_dairy": "cat_dairy_milk",
            "cat_meat": "cat_meat_fresh-meat",
            "cat_frozen": "cat_frozen_ready-meals",
            "cat_bakery": "cat_bakery_bread",
            "cat_baby-food": "cat_baby-food_purees",
            "cat_snacks": "cat_snacks_crackers",
            "cat_fast-food-to-go": "cat_fast-food-to-go_wraps-sandwiches",
            "cat_household": "cat_household_cleaning",
            "cat_beverages": "cat_beverages_soft-drinks",
        }

    @staticmethod
    def _normalize(text):
        txt = (text or "").lower()
        txt = re.sub(r"[^a-z0-9\s\-]", " ", txt)
        return re.sub(r"\s+", " ", txt).strip()

    def map_category(self, store_category_path):
        """Backwards-compatible method returning a friendly root label."""
        result = self.map_category_with_path(store_category_path)
        root = result.get("root")
        labels = {
            "cat_produce": "Produce",
            "cat_pantry": "Pantry",
            "cat_dairy": "Dairy",
            "cat_meat": "Meat",
            "cat_frozen": "Frozen",
            "cat_bakery": "Bakery",
            "cat_baby-food": "Baby food",
            "cat_snacks": "Snacks",
            "cat_fast-food-to-go": "Fast Food & To Go",
            "cat_household": "Household",
            "cat_beverages": "Beverages",
        }
        return labels.get(root, "Pantry")

    def map_category_with_path(self, store_category_path):
        """Map store path text to production taxonomy IDs and path."""
        if isinstance(store_category_path, list):
            text = " ".join([str(x) for x in store_category_path])
        else:
            text = str(store_category_path or "")

        text = self._normalize(text)
        best_leaf = None
        best_score = -1

        for leaf_id, (root_id, keywords) in self.leaf_rules.items():
            score = 0
            for kw in keywords:
                kw_n = self._normalize(kw)
                if kw_n and kw_n in text:
                    score += 2 + min(3, len(kw_n.split()))
            if score > best_score:
                best_score = score
                best_leaf = leaf_id

        if best_leaf is None:
            best_leaf = "cat_pantry_sauces-condiments"

        root = self.leaf_rules.get(best_leaf, ("cat_pantry", []))[0]
        return {
            "root": root,
            "categoryId": best_leaf,
            "categoryPath": [root, best_leaf],
        }

    def _ai_fallback_prediction(self, text):
        """Deprecated placeholder kept for compatibility."""
        _ = text
        return "Pantry"
