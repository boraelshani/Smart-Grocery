"""Category normalization helpers.

This module provides a richer keyword mapper for assigning both a leaf
category and its path under the production taxonomy with confidence scoring.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher


class CategoryMapper:
    def __init__(self):
        # Leaf -> (root, keywords)
        self.leaf_rules = {
            "cat_produce_fruits": ("cat_produce", ["fruit", "obst", "apple", "banana", "kiwi", "berry", "orange", "pear", "apples", "pears"]),
            "cat_produce_vegetables": ("cat_produce", ["vegetable", "gemuse", "carrot", "tomato", "broccoli", "pepper", "onion", "vegetables"]),
            "cat_dairy_milk": ("cat_dairy", ["milk", "milch", "lactose", "whole milk", "skim", "2% milk", "vollmilch"]),
            "cat_dairy_yogurt": ("cat_dairy", ["yogurt", "joghurt", "skyr", "pudding", "yoghurt"]),
            "cat_dairy_cheese": ("cat_dairy", ["cheese", "kase", "käse", "mozzarella", "gouda", "cheddar", "parmesan"]),
            "cat_dairy_eggs": ("cat_dairy", ["egg", "eier", "eggs"]),
            "cat_dairy_butter": ("cat_dairy", ["butter", "margarine"]),
            "cat_meat_poultry": ("cat_meat", ["chicken", "turkey", "poultry", "geflugel", "geflügel", "huhn", "hähnchen"]),
            "cat_meat_sausages-coldcuts": ("cat_meat", ["salami", "ham", "sausage", "wurst", "cold cut", "bologna", "bacon", "schinken"]),
            "cat_meat_seafood": ("cat_meat", ["fish", "fisch", "salmon", "tuna", "shrimp", "seafood", "lachs", "thunfisch"]),
            "cat_meat_fresh-meat": ("cat_meat", ["beef", "pork", "lamb", "veal", "fleisch", "rindfleisch", "schweinefleisch", "burger", "patty", "grill", "grillies", "grillgut"]),
            "cat_frozen_pizza": ("cat_frozen", ["frozen pizza", "pizza", "margherita", "tiefkühlpizza"]),
            "cat_frozen_ice-cream": ("cat_frozen", ["ice cream", "gelato", "sorbet", "eis", "eiscreme"]),
            "cat_frozen_ready-meals": ("cat_frozen", ["frozen", "ready meal", "lasagna", "nuggets", "tiefkühl"]),
            "cat_bakery_bread": ("cat_bakery", ["bread", "brot", "loaf", "toast", "vollkornbrot"]),
            "cat_bakery_rolls-buns": ("cat_bakery", ["roll", "bun", "semmel", "weckerl", "bagel", "brötchen"]),
            "cat_bakery_pastries": ("cat_bakery", ["croissant", "pastry", "strudel", "danish", "gebäck"]),
            "cat_baby-food_purees": ("cat_baby-food", ["baby puree", "baby food", "puree", "brei", "babybrei"]),
            "cat_baby-food_formula": ("cat_baby-food", ["formula", "infant milk", "pre milk", "babymilch"]),
            "cat_snacks_chips": ("cat_snacks", ["chips", "crisps", "pringles", "nacho", "kartoffelchips"]),
            "cat_snacks_protein-bars": ("cat_snacks", ["protein bar", "energy bar", "riegel", "proteinriegel"]),
            "cat_snacks_sweets": ("cat_snacks", ["chocolate", "candy", "sweets", "gummy", "cookie", "biscuit", "schokolade", "süßigkeiten", "keks"]),
            "cat_snacks_crackers": ("cat_snacks", ["cracker", "pretzel", "bruschetta", "snack", "salzstangen"]),
            "cat_fast-food-to-go_wraps-sandwiches": ("cat_fast-food-to-go", ["wrap", "sandwich", "baguette", "panini"]),
            "cat_fast-food-to-go_salads-bowls": ("cat_fast-food-to-go", ["salad bowl", "caesar", "bowl", "salat"]),
            "cat_household_cleaning": ("cat_household", ["cleaner", "detergent", "dish soap", "bleach", "reiniger", "putzmittel"]),
            "cat_household_paper-hygiene": ("cat_household", ["toilet paper", "tissue", "paper towel", "napkin", "toilettenpapier", "küchenpapier"]),
            "cat_household_laundry": ("cat_household", ["laundry", "washing powder", "fabric softener", "waschmittel", "weichspüler"]),
            "cat_beverages_water": ("cat_beverages", ["water", "mineralwasser", "sparkling water", "wasser"]),
            "cat_beverages_soft-drinks": ("cat_beverages", ["cola", "soft drink", "soda", "limonade", "limo"]),
            "cat_beverages_juice-nectar": ("cat_beverages", ["juice", "saft", "nectar", "orangensaft"]),
            "cat_beverages_coffee": ("cat_beverages", ["coffee", "kaffee", "espresso", "nescafe", "cappuccino"]),
            "cat_beverages_tea": ("cat_beverages", ["tea", "tee", "iced tea", "eistee"]),
            "cat_beverages_beer": ("cat_beverages", ["beer", "bier", "lager", "pils"]),
            "cat_pantry_pasta": ("cat_pantry", ["pasta", "nudeln", "spaghetti", "penne", "fusilli"]),
            "cat_pantry_rice": ("cat_pantry", ["rice", "reis", "basmati", "risotto"]),
            "cat_pantry_oil": ("cat_pantry", ["oil", "öl", "olive oil", "olivenöl", "sunflower oil"]),
            "cat_pantry_sauces": ("cat_pantry", ["sauce", "soße", "ketchup", "mayo", "mayonnaise", "bbq sauce"]),
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

    def _calculate_confidence(self, score, text_length):
        """Calculate confidence score (0-100) based on keyword matches and text length."""
        if score == 0:
            return 0
        
        # Base confidence from score
        base_confidence = min(100, score * 10)
        
        # Adjust based on text length (more text = more context = higher confidence)
        length_factor = min(1.0, text_length / 50)  # Cap at 50 characters
        
        # Final confidence
        confidence = int(base_confidence * (0.7 + 0.3 * length_factor))
        return min(100, max(0, confidence))

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

    def map_category_with_path(self, store_category_path, product_name="", product_description=""):
        """Map store path text to production taxonomy IDs and path with confidence score.
        
        Args:
            store_category_path: Category path from the store (e.g., "Food > Dairy > Milk")
            product_name: Product name for additional context
            product_description: Product description for additional context
            
        Returns:
            dict with keys: root, categoryId, categoryPath, confidence, matched_keywords
        """
        if isinstance(store_category_path, list):
            text = " ".join([str(x) for x in store_category_path])
        else:
            text = str(store_category_path or "")

        # Combine all available text for better matching
        combined_text = f"{text} {product_name} {product_description}"
        normalized_text = self._normalize(combined_text)
        text_length = len(normalized_text)
        
        best_leaf = None
        best_score = -1
        matched_keywords = []

        for leaf_id, (root_id, keywords) in self.leaf_rules.items():
            score = 0
            leaf_matches = []
            for kw in keywords:
                kw_n = self._normalize(kw)
                if kw_n and kw_n in normalized_text:
                    # Score based on keyword length and specificity
                    keyword_score = 2 + min(3, len(kw_n.split()))
                    score += keyword_score
                    leaf_matches.append(kw)
            
            if score > best_score:
                best_score = score
                best_leaf = leaf_id
                matched_keywords = leaf_matches

        # Calculate confidence
        confidence = self._calculate_confidence(best_score, text_length)
        
        # If confidence is too low, use fallback
        if best_leaf is None or confidence < 30:
            best_leaf = "cat_pantry_sauces-condiments"
            confidence = 20  # Low confidence for fallback

        root = self.leaf_rules.get(best_leaf, ("cat_pantry", []))[0]
        
        return {
            "root": root,
            "categoryId": best_leaf,
            "categoryPath": [root, best_leaf],
            "confidence": confidence,
            "matched_keywords": matched_keywords[:5],  # Limit to top 5 matches
        }

    def suggest_categories(self, product_name, product_description="", store_category_path="", top_n=3):
        """Suggest multiple category matches with confidence scores.
        
        Args:
            product_name: Product name
            product_description: Product description
            store_category_path: Category path from store
            top_n: Number of suggestions to return
            
        Returns:
            list of dicts with keys: categoryId, confidence, matched_keywords
        """
        combined_text = f"{store_category_path} {product_name} {product_description}"
        normalized_text = self._normalize(combined_text)
        text_length = len(normalized_text)
        
        suggestions = []
        
        for leaf_id, (root_id, keywords) in self.leaf_rules.items():
            score = 0
            leaf_matches = []
            for kw in keywords:
                kw_n = self._normalize(kw)
                if kw_n and kw_n in normalized_text:
                    keyword_score = 2 + min(3, len(kw_n.split()))
                    score += keyword_score
                    leaf_matches.append(kw)
            
            if score > 0:
                confidence = self._calculate_confidence(score, text_length)
                suggestions.append({
                    "categoryId": leaf_id,
                    "root": root_id,
                    "confidence": confidence,
                    "matched_keywords": leaf_matches[:5],
                    "score": score
                })
        
        # Sort by confidence descending
        suggestions.sort(key=lambda x: x["confidence"], reverse=True)
        
        return suggestions[:top_n]

    def _ai_fallback_prediction(self, text):
        """Deprecated placeholder kept for compatibility."""
        _ = text
        return "Pantry"

