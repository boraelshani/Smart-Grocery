#!/usr/bin/env python3
"""
Step 2 – Strong Keyword-Based Product Categorisation
════════════════════════════════════════════════════

Assigns each product to a full hierarchical category path with high
confidence. Works on both English and German names.

Category tree:
  Level 1 (8 departments):
    Dairy & Eggs
    Fresh Produce
    Meat & Fish
    Bakery & Bread
    Pantry & Staples
    Beverages
    Snacks & Sweets
    Frozen
    Household & Personal Care
    Baby & Kids
    Pets

  Level 2 (30+ subcategories):
    e.g. Dairy & Eggs > Milk, Cheese, Yogurt, Butter & Cream, Eggs

Confidence scoring:
  0.9–1.0: Multiple strong keyword matches (auto-assign)
  0.6–0.89: Single strong match or multiple weak (auto-assign)
  0.3–0.59: Weak match (review queue)
  <0.3: No match (uncategorized)

Usage:
  python scripts/pipeline/categoriser.py --dry-run --limit 30
  python scripts/pipeline/categoriser.py
"""

import os
import re
import sys
from pathlib import Path
from collections import defaultdict

_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv
load_dotenv(_project_root / ".env", override=True)

# ───────────────────────────────────────────────────────────────────────
# CATEGORY TREE
# ───────────────────────────────────────────────────────────────────────

# Each category has a unique ID, a human-readable path, and keyword lists.
# Keywords are tuples: (keyword_string, weight, language)
# weight: 1.0 = exact/definitive, 0.8 = strong, 0.5 = moderate, 0.3 = weak
# language: "de", "en", "both"

CATEGORIES = {
    # ═══════════ DAIRY & EGGS ═══════════
    "cat_dairy_milk": {
        "path": ["Dairy & Eggs", "Milk"],
        "keywords": [
            ("vollmilch", 1.0, "de"), ("milch", 0.8, "both"),
            ("frischmilch", 1.0, "de"), ("heumilch", 1.0, "de"),
            ("biomilch", 1.0, "de"), ("haltbarmilch", 1.0, "de"),
            ("buttermilch", 1.0, "both"), ("laktosefrei milch", 1.0, "de"),
            ("sojamilch", 0.7, "both"), ("mandelmilch", 0.7, "both"),
            ("hafermilch", 0.8, "de"), ("oat milk", 0.8, "en"),
            ("dinkelmilch", 0.8, "de"), ("reis milch", 0.8, "both"),
            ("kokosmilch", 0.8, "de"), ("coconut milk", 0.8, "en"),
            ("kakao milch", 0.7, "de"), ("schokoladenmilch", 1.0, "de"),
            ("chocolate milk", 1.0, "en"), ("espressomilch", 0.8, "de"),
            ("barista milk", 0.7, "en"), ("barista edition", 0.6, "en"),
            ("milch drink", 0.7, "de"), ("trinkmilch", 0.9, "de"),
            ("lichtmilch", 0.8, "de"), ("bauernmilch", 0.9, "de"),
            ("condensed milk", 0.8, "en"), ("kondensmilch", 0.9, "de"),
            ("evaporated milk", 0.8, "en"),
            ("0.9%", 0.7, "both"), ("1.5%", 0.7, "both"), ("3.5%", 0.7, "both"),
            ("skimmed milk", 0.8, "en"), ("entrahmte milch", 0.9, "de"),
            ("teilentrahmt", 0.7, "de"),
        ],
    },
    "cat_dairy_cheese": {
        "path": ["Dairy & Eggs", "Cheese"],
        "keywords": [
            ("kase", 0.9, "de"), ("kaese", 0.9, "de"), ("cheese", 0.5, "en"),
            ("gouda", 0.9, "both"), ("edamer", 0.9, "both"),
            ("emmentaler", 0.9, "both"), ("emmenthaler", 0.9, "both"),
            ("mozzarella", 1.0, "both"), ("feta", 0.9, "both"),
            ("parmesan", 0.9, "both"), ("brie", 0.9, "both"),
            ("camembert", 0.9, "both"), ("ricotta", 0.9, "both"),
            ("topfen", 0.8, "de"), ("quark", 0.6, "both"),
            ("frischkase", 1.0, "de"), ("frischkase", 1.0, "de"),
            ("frischkäse", 1.0, "de"), ("cream cheese", 0.9, "en"),
            ("hirtenkase", 1.0, "de"), ("hirtenkase", 1.0, "de"),
            ("schafskase", 1.0, "de"), ("sheep cheese", 0.8, "en"),
            ("schmelzkase", 0.8, "de"), ("processed cheese", 0.7, "en"),
            ("streichkase", 0.8, "de"), ("raclette", 0.9, "both"),
            ("grillkase", 1.0, "de"), ("grill cheese", 0.7, "en"),
            ("handkase", 0.9, "de"), ("bergkase", 0.9, "de"),
            ("tilsiter", 0.9, "both"), ("gorgonzola", 0.9, "both"),
            ("blue cheese", 0.8, "en"), ("blauschimmelkase", 1.0, "de"),
            ("appenzeller", 0.9, "both"), ("gruyere", 0.9, "both"),
            ("gruyère", 0.9, "both"), ("cheese slices", 0.7, "en"),
            ("scheibenkase", 0.9, "de"), ("wurfelskase", 0.8, "de"),
            ("cheese cubes", 0.7, "en"), ("reibekase", 0.8, "de"),
            ("grated cheese", 0.8, "en"), ("parmesan gerieben", 0.9, "de"),
        ],
    },
    "cat_dairy_yogurt": {
        "path": ["Dairy & Eggs", "Yogurt & Desserts"],
        "keywords": [
            ("yogurt", 1.0, "both"), ("joghurt", 1.0, "de"),
            ("griechischer joghurt", 1.0, "de"), ("greek yogurt", 1.0, "en"),
            ("skyr", 1.0, "both"), ("probiotic", 0.5, "en"),
            ("probiotisch", 0.6, "de"), ("trinkjoghurt", 1.0, "de"),
            ("drink yogurt", 0.9, "en"), ("milchreis", 0.8, "de"),
            ("rice pudding", 0.8, "en"), ("pudding", 0.7, "both"),
            ("dessert", 0.4, "both"), ("mousse au chocolat", 0.8, "both"),
            ("vanille creme", 0.7, "de"), ("vanilla cream", 0.7, "en"),
            ("quarkspeise", 0.9, "de"), ("quark speise", 0.9, "de"),
            ("fruchtjoghurt", 0.9, "de"), ("fruit yogurt", 0.8, "en"),
            ("natural yogurt", 0.7, "en"), ("naturjoghurt", 0.9, "de"),
        ],
    },
    "cat_dairy_butter": {
        "path": ["Dairy & Eggs", "Butter & Cream"],
        "keywords": [
            ("butter", 0.9, "both"), ("margarine", 0.9, "both"),
            ("rahm", 0.7, "de"), ("sahne", 0.7, "both"),
            ("obers", 0.8, "de"), ("schlagsahne", 1.0, "de"),
            ("whipping cream", 0.9, "en"), ("kochsahne", 1.0, "de"),
            ("cooking cream", 0.8, "en"), ("creme fraiche", 0.9, "both"),
            ("creme fraîche", 0.9, "both"), ("schmand", 0.8, "both"),
            ("buttermilch", 0.5, "both"), ("schlagobers", 0.9, "de"),
            ("saure sahne", 0.8, "de"), ("sour cream", 0.8, "en"),
            ("butter milch", 0.6, "de"),
        ],
    },
    "cat_dairy_eggs": {
        "path": ["Dairy & Eggs", "Eggs"],
        "keywords": [
            ("eier", 1.0, "de"), ("ei ", 0.8, "de"), (" eggs", 0.8, "en"),
            (" eggs ", 0.8, "en"), ("freilandei", 1.0, "de"),
            ("free range egg", 0.9, "en"), ("bioei", 1.0, "de"),
            ("organic egg", 0.8, "en"), ("bodeneier", 1.0, "de"),
            ("barn eggs", 0.8, "en"), ("eier 6", 0.9, "de"),
            ("eier 10", 0.9, "de"), ("eier 12", 0.9, "de"),
            ("10 pack eggs", 0.8, "en"), ("dozen eggs", 0.7, "en"),
        ],
    },

    # ═══════════ FRESH PRODUCE ═══════════
    "cat_produce_fruit": {
        "path": ["Fresh Produce", "Fresh Fruits"],
        "keywords": [
            ("apfel", 0.9, "de"), ("apple", 0.8, "en"),
            ("banane", 0.9, "de"), ("banana", 0.8, "en"), ("bananas", 0.8, "en"),
            ("orange", 0.8, "both"), ("oranges", 0.8, "en"),
            ("mandarine", 0.9, "de"), ("clementine", 0.9, "both"),
            ("zitrone", 0.9, "de"), ("lemon", 0.8, "en"), ("lemons", 0.8, "en"),
            ("birne", 0.9, "de"), ("pear", 0.8, "en"),
            ("pfirsich", 0.9, "de"), ("peach", 0.8, "en"),
            ("aprikose", 0.9, "de"), ("marille", 0.9, "de"),
            ("nectarine", 0.9, "both"), ("kiwi", 0.9, "both"),
            ("kiwis", 0.9, "en"), ("ananas", 0.9, "both"),
            ("pineapple", 0.8, "en"), ("mango", 0.9, "both"),
            ("wassermelone", 1.0, "de"), ("watermelon", 0.9, "en"),
            ("melon", 0.7, "both"), ("grapefruit", 0.9, "both"),
            ("himbeere", 0.9, "de"), ("raspberry", 0.8, "en"),
            ("erdbeere", 0.9, "de"), ("strawberry", 0.8, "en"),
            ("strawberries", 0.8, "en"),
            ("blaubeere", 0.9, "de"), ("heidelbeere", 0.9, "de"),
            ("blueberry", 0.8, "en"), ("blueberries", 0.8, "en"),
            ("traube", 0.8, "de"), ("grape", 0.7, "en"), ("grapes", 0.7, "en"),
            ("kirsche", 0.9, "de"), ("cherry", 0.8, "en"), ("cherries", 0.8, "en"),
            ("pflaume", 0.9, "de"), ("plum", 0.8, "en"),
            ("obst", 0.3, "de"), ("fruit", 0.2, "en"),
            ("avocado", 0.9, "both"), ("granatapfel", 0.9, "de"),
            ("pomegranate", 0.8, "en"), ("passionsfrucht", 0.9, "de"),
            ("passion fruit", 0.8, "en"), ("limette", 0.9, "de"),
            ("lime", 0.8, "en"), ("datteln", 0.8, "de"),
            ("dates", 0.7, "en"), ("datteln ohne stein", 0.9, "de"),
            ("frucht mix", 0.6, "de"), ("fruit mix", 0.6, "en"),
            ("beeren", 0.7, "de"), ("berries", 0.7, "en"),
            ("apricot", 0.8, "en"), ("apricots", 0.8, "en"),
        ],
    },
    "cat_produce_vegetable": {
        "path": ["Fresh Produce", "Fresh Vegetables"],
        "keywords": [
            ("tomate", 0.9, "de"), ("tomato", 0.8, "en"), ("tomatoes", 0.8, "en"),
            ("gurke", 0.9, "de"), ("cucumber", 0.8, "en"),
            ("paprika", 0.8, "both"), ("salat", 0.7, "de"),
            ("eisbergsalat", 1.0, "de"), ("karotte", 0.9, "de"),
            ("karotten", 0.9, "de"), ("carrot", 0.8, "en"), ("carrots", 0.8, "en"),
            ("erdapfel", 0.8, "de"), ("erdäpfel", 0.8, "de"),
            ("kartoffel", 0.8, "de"), ("potato", 0.7, "en"), ("potatoes", 0.7, "en"),
            ("zwiebel", 0.9, "de"), ("onion", 0.8, "en"), ("onions", 0.8, "en"),
            ("lauch", 0.7, "de"), ("porree", 0.8, "de"), ("leek", 0.8, "en"),
            ("zucchini", 0.9, "both"), ("aubergine", 0.9, "both"),
            ("melanzani", 0.9, "de"), ("brokkoli", 0.9, "de"),
            ("broccoli", 0.9, "both"), ("blumenkohl", 0.9, "de"),
            ("cauliflower", 0.8, "en"), ("spinat", 0.9, "both"),
            ("kohl", 0.5, "de"), ("cabbage", 0.7, "en"),
            ("kraut", 0.4, "de"), ("kurbis", 0.8, "de"), ("kürbis", 0.8, "de"),
            ("pumpkin", 0.7, "en"), ("gemuse", 0.3, "de"),
            ("vegetable", 0.2, "en"), ("champignon", 0.9, "both"),
            ("champignons", 0.9, "both"), ("mushroom", 0.7, "en"),
            ("pilze", 0.6, "de"), ("rettich", 0.8, "de"),
            ("radicchio", 0.8, "both"), ("rucola", 0.9, "both"),
            ("arugula", 0.8, "en"), ("radieschen", 0.9, "de"),
            ("sellerie", 0.8, "de"), ("celery", 0.7, "en"),
            ("fenchel", 0.8, "both"), ("knoblauch", 0.8, "de"),
            ("garlic", 0.7, "en"), ("mais", 0.6, "de"), ("corn", 0.6, "en"),
            ("spargel", 0.9, "both"), ("asparagus", 0.8, "en"),
            ("bohne", 0.5, "de"), ("bean", 0.5, "en"), ("beans", 0.5, "en"),
            ("linse", 0.5, "de"), ("lentil", 0.5, "en"),
            ("peperoni", 0.6, "both"), ("chili", 0.6, "both"),
            ("ingwer", 0.7, "de"), ("ginger", 0.7, "en"),
            ("lettuce", 0.8, "en"), ("spinach", 0.7, "en"),
            ("arugula", 0.8, "en"), ("cilantro", 0.7, "en"),
            ("coriander", 0.7, "en"), ("kale", 0.7, "en"),
            ("radish", 0.7, "en"), ("radishes", 0.7, "en"),
            ("sprout", 0.5, "en"), ("sprouts", 0.5, "en"),
            ("citrus", 0.5, "en"), ("lamb", 0.7, "en"),
            ("veal", 0.7, "en"), ("ground meat", 0.7, "en"),
        ],
    },
    "cat_produce_herbs": {
        "path": ["Fresh Produce", "Herbs & Spices"],
        "keywords": [
            ("basilikum", 0.9, "de"), ("basil", 0.8, "en"),
            ("oregano", 0.8, "both"), ("thymian", 0.8, "de"),
            ("thyme", 0.8, "en"), ("rosmarin", 0.8, "de"),
            ("rosemary", 0.8, "en"), ("petersilie", 0.9, "de"),
            ("parsley", 0.8, "en"), ("schnittlauch", 0.9, "de"),
            ("chives", 0.8, "en"), ("minze", 0.8, "de"),
            ("mint", 0.7, "en"), ("dill", 0.8, "both"),
            ("koriander", 0.8, "de"), ("coriander", 0.8, "en"),
            ("salbei", 0.8, "de"), ("sage", 0.7, "en"),
            ("lauchkrauter", 0.7, "de"), ("krauter", 0.4, "de"),
            ("herbs", 0.3, "en"), ("krautermix", 0.6, "de"),
        ],
    },

    # ═══════════ MEAT & FISH ═══════════
    "cat_meat_poultry": {
        "path": ["Meat & Fish", "Poultry"],
        "keywords": [
            ("hahnchen", 1.0, "de"), ("haehnchen", 1.0, "de"),
            ("hendl", 0.9, "de"), ("chicken", 0.8, "en"),
            ("hahnchenbrust", 1.0, "de"), ("chicken breast", 0.9, "en"),
            ("putenbrust", 1.0, "de"), ("turkey breast", 0.9, "en"),
            ("pute", 0.8, "de"), ("turkey", 0.8, "en"),
            ("truthahn", 0.8, "de"), ("wings", 0.5, "en"),
            ("chicken wings", 0.8, "en"), ("drumstick", 0.6, "en"),
            ("keule", 0.5, "de"), ("nugget", 0.5, "both"),
            ("chicken nuggets", 0.7, "en"), ("geschnetzeltes", 0.5, "de"),
            ("chicken caesar wrap", 0.6, "en"),
            ("pute", 0.8, "de"), ("puten", 0.7, "de"),
            ("putenflügerl", 0.9, "de"), ("putenflugel", 0.9, "de"),
            ("putenoberkeule", 0.8, "de"), ("putenunterkeule", 0.8, "de"),
            ("putenbrust", 0.9, "de"), ("entenkeule", 0.8, "de"),
            ("duck", 0.7, "en"), ("duck leg", 0.7, "en"),
            ("entenbrust", 0.8, "de"), ("gans", 0.8, "de"),
            ("goose", 0.8, "en"), ("gansl", 0.8, "de"),
            ("backerl", 0.5, "de"), ("backl", 0.5, "de"),
            ("oberkeule", 0.5, "de"), ("unterkeule", 0.5, "de"),
        ],
    },
    "cat_meat_beef_pork": {
        "path": ["Meat & Fish", "Beef & Pork"],
        "keywords": [
            ("rind", 0.7, "de"), ("schwein", 0.7, "de"),
            ("beef", 0.7, "en"), ("pork", 0.7, "en"),
            ("steak", 0.8, "both"), ("schnitzel", 0.9, "de"),
            ("gulasch", 0.8, "de"), ("goulash", 0.8, "en"),
            ("hackfleisch", 1.0, "de"), ("faschiertes", 1.0, "de"),
            ("minced meat", 0.8, "en"), ("ground beef", 0.8, "en"),
            ("filet", 0.6, "both"), ("roulade", 0.7, "both"),
            ("schweinsbraten", 1.0, "de"), ("rostbraten", 0.9, "de"),
            ("geschnetzeltes", 0.7, "de"), ("sliced meat", 0.6, "en"),
            ("wurfstel", 0.7, "de"), ("wurstel", 0.7, "de"),
            ("frankfurter", 0.7, "both"), ("debreziner", 0.8, "de"),
            ("kasekrainer", 0.8, "de"),
            ("kalb", 0.8, "de"), ("veal", 0.7, "en"),
            ("kalbstafelspitz", 0.9, "de"), ("kalbs", 0.6, "de"),
            ("rindsbackerl", 0.9, "de"), ("rinds", 0.5, "de"),
            ("tafelspitz", 0.9, "de"), ("beef roast", 0.7, "en"),
            ("kalbstelze", 0.9, "de"), ("beef shank", 0.7, "en"),
            ("kalbsrack", 0.8, "de"), ("kalbsleber", 0.8, "de"),
            ("rindsschmorbraten", 0.8, "de"), ("rindsrippe", 0.8, "de"),
            ("rindsgulasch", 0.8, "de"), ("beef goulash", 0.7, "en"),
            ("rinderrouladen", 0.8, "de"), ("beef roulade", 0.7, "en"),
            ("lamm", 0.7, "de"), ("lammkeule", 0.8, "de"),
            ("lammrücken", 0.8, "de"), ("lammkotelett", 0.8, "de"),
            ("hirsch", 0.8, "de"), ("wildschwein", 0.8, "de"),
            ("reh", 0.7, "de"), ("wildbret", 0.8, "de"),
            ("game meat", 0.7, "en"), ("venison", 0.8, "en"),
            ("schnitzel", 0.7, "de"), ("gulasch", 0.7, "de"),
            ("rollbraten", 0.7, "de"), ("ragout", 0.7, "de"),
            ("knödel", 0.7, "de"), ("knoedel", 0.7, "de"),
            ("grammelknödel", 0.8, "de"), ("heurigenknödel", 0.8, "de"),
            ("leberknödel", 0.8, "de"), ("semmelknödel", 0.8, "de"),
            ("praline", 0.7, "both"), ("pralinen", 0.7, "de"),
            ("nusstasche", 0.7, "de"), ("aufstrich", 0.6, "de"),
            ("cremeschnitten", 0.8, "de"), ("kardinalschnitten", 0.8, "de"),
        ],
    },
    "cat_meat_deli": {
        "path": ["Meat & Fish", "Deli & Cold Cuts"],
        "keywords": [
            ("salami", 0.9, "both"), ("schinken", 0.9, "de"),
            ("ham", 0.8, "en"), ("wurst", 0.5, "de"),
            ("sausage", 0.5, "en"), ("speck", 0.8, "de"),
            ("bacon", 0.7, "en"), ("aufschnitt", 0.8, "de"),
            ("cold cuts", 0.7, "en"), ("mortadella", 0.8, "both"),
            ("bresaola", 0.8, "both"), ("prosciutto", 0.8, "both"),
            ("lyoner", 0.8, "both"), ("extrawurst", 1.0, "de"),
            ("salsiz", 0.8, "both"), ("landjager", 0.8, "de"),
            ("landjäger", 0.8, "de"), ("leberkase", 0.8, "de"),
            ("leberkäse", 0.8, "de"), ("wurstsalat", 0.8, "de"),
            ("sausage salad", 0.7, "en"), ("hering", 0.6, "de"),
            ("herring", 0.6, "en"),
        ],
    },
    "cat_meat_fish": {
        "path": ["Meat & Fish", "Fish & Seafood"],
        "keywords": [
            ("fisch", 0.6, "de"), ("fish", 0.6, "en"),
            ("salmon", 0.9, "en"), ("lachs", 0.9, "de"),
            ("thunfisch", 1.0, "de"), ("tuna", 0.9, "en"),
            ("forelle", 0.9, "de"), ("trout", 0.8, "en"),
            ("kabeljau", 0.9, "de"), ("cod", 0.8, "en"),
            ("seelachs", 0.8, "de"), ("pollock", 0.8, "en"),
            ("scholle", 0.8, "de"), ("plaice", 0.7, "en"),
            ("shrimp", 0.9, "en"), ("garnelen", 0.9, "de"),
            ("prawn", 0.8, "en"), ("meeresfruchte", 0.8, "de"),
            ("seafood", 0.7, "en"), ("matjes", 0.8, "de"),
            ("hering", 0.6, "de"), ("fischstabchen", 0.9, "de"),
            ("fischfilet", 0.9, "de"), ("fischstäbchen", 0.9, "de"),
        ],
    },

    # ═══════════ BAKERY & BREAD ═══════════
    "cat_bakery_bread": {
        "path": ["Bakery & Bread", "Bread"],
        "keywords": [
            ("brot", 0.7, "de"), ("bread", 0.6, "en"),
            ("weckerl", 0.9, "de"), ("semmel", 0.9, "de"),
            ("brötchen", 0.8, "de"), ("vollkornbrot", 1.0, "de"),
            ("weissbrot", 0.9, "de"), ("weißbrot", 0.9, "de"),
            ("white bread", 0.8, "en"), ("schwarzbrot", 0.9, "de"),
            ("grauerl", 0.9, "de"), ("toastbrot", 0.9, "de"),
            ("toast bread", 0.8, "en"), ("krustenbrot", 0.9, "de"),
            ("bauernbrot", 0.9, "de"), ("landbrot", 0.9, "de"),
            ("ciabatta", 0.8, "both"), ("baguette", 0.8, "both"),
            ("ciabatta bread", 0.7, "en"), ("italian ciabatta", 0.7, "en"),
        ],
    },
    "cat_bakery_pastry": {
        "path": ["Bakery & Bread", "Pastries & Cakes"],
        "keywords": [
            ("kuchen", 0.6, "de"), ("cake", 0.6, "en"),
            ("torte", 0.7, "both"), ("geback", 0.6, "de"),
            ("pastry", 0.5, "en"), ("strudel", 0.8, "both"),
            ("croissant", 0.9, "both"), ("kipferl", 0.9, "de"),
            ("brioche", 0.9, "both"), ("muffin", 0.9, "both"),
            ("plunder", 0.7, "de"), ("danish", 0.6, "en"),
            ("butter croissant", 0.9, "en"), ("blatteteig", 0.8, "de"),
            ("puff pastry", 0.8, "en"), ("pizza dough", 0.8, "en"),
            ("pizzateig", 0.9, "de"),
            ("donut", 0.9, "both"), ("donuts", 0.9, "en"),
            ("doughnut", 0.9, "both"), ("doughnuts", 0.9, "en"),
        ],
    },

    # ═══════════ PANTRY & STAPLES ═══════════
    "cat_pantry_pasta": {
        "path": ["Pantry & Staples", "Pasta & Noodles"],
        "keywords": [
            ("nudel", 0.7, "de"), ("nudeln", 0.7, "de"),
            ("pasta", 0.8, "both"), ("spaghetti", 0.9, "both"),
            ("penne", 0.9, "both"), ("fusilli", 0.9, "both"),
            ("tagliatelle", 0.9, "both"), ("lasagne", 0.9, "both"),
            ("tortellini", 0.9, "both"), ("ravioli", 0.9, "both"),
            ("macaroni", 0.9, "both"), ("spatzle", 0.8, "de"),
            ("noodle", 0.7, "en"), ("noodles", 0.7, "en"),
            ("instant noodles", 0.8, "en"), ("ramen", 0.8, "en"),
            ("udon", 0.8, "en"), ("soba", 0.8, "en"),
        ],
    },
    "cat_pantry_rice_grains": {
        "path": ["Pantry & Staples", "Rice & Grains"],
        "keywords": [
            ("reis", 0.8, "de"), ("rice", 0.8, "en"),
            ("basmati", 0.9, "both"), ("jasmin", 0.7, "both"),
            ("parboiled", 0.8, "both"), ("naturreis", 0.9, "de"),
            ("wildreis", 0.9, "de"), ("wild rice", 0.8, "en"),
            ("couscous", 0.9, "both"), ("bulgur", 0.9, "both"),
            ("quinoa", 0.9, "both"), ("dinkel", 0.8, "de"),
            ("spelt", 0.7, "en"), ("haferflocken", 1.0, "de"),
            ("oats", 0.7, "en"), ("oatmeal", 0.8, "en"),
            ("porridge", 0.7, "both"), ("milchreis", 0.5, "de"),
            ("polenta", 0.8, "both"), ("grieß", 0.8, "de"),
            ("semolina", 0.7, "en"), ("granola", 0.8, "en"),
            ("muesli", 0.8, "both"), ("müsli", 0.8, "de"),
            ("cornflakes", 0.8, "en"), ("cereal", 0.6, "en"),
            ("frühstück", 0.5, "de"), ("breakfast", 0.5, "en"),
        ],
    },
    "cat_pantry_oil_vinegar": {
        "path": ["Pantry & Staples", "Oils & Vinegars"],
        "keywords": [
            ("olivenol", 0.9, "de"), ("olive oil", 0.9, "en"),
            ("extra virgin", 0.7, "en"), ("sonnenblumenol", 1.0, "de"),
            ("sunflower oil", 0.8, "en"), ("rapswol", 0.8, "de"),
            ("rapsoel", 0.8, "de"), ("rapeseed oil", 0.8, "en"),
            ("kurbiskernol", 1.0, "de"), ("pumpkin seed oil", 0.8, "en"),
            ("walnussol", 0.8, "de"), ("walnut oil", 0.8, "en"),
            ("ol", 0.4, "de"), ("oil", 0.3, "en"),
            ("essig", 0.7, "de"), ("vinegar", 0.7, "en"),
            ("balsamico", 0.9, "both"), ("aceto balsamico", 0.9, "both"),
            ("apfelessig", 0.8, "de"), ("apple cider vinegar", 0.8, "en"),
            ("weinessig", 0.8, "de"), ("wine vinegar", 0.8, "en"),
        ],
    },
    "cat_pantry_sauces": {
        "path": ["Pantry & Staples", "Sauces & Condiments"],
        "keywords": [
            ("sauce", 0.4, "both"), ("ketchup", 0.9, "both"),
            ("mayonnaise", 0.9, "both"), ("senf", 0.9, "de"),
            ("mustard", 0.8, "en"), ("sojasauce", 0.9, "de"),
            ("soy sauce", 0.8, "en"), ("tabasco", 0.8, "both"),
            ("pesto", 0.9, "both"), ("bolognese", 0.7, "both"),
            ("tomatensauce", 0.9, "de"), ("tomato sauce", 0.8, "en"),
            ("arrabiata", 0.8, "both"), ("salatdressing", 0.9, "de"),
            ("dressing", 0.5, "en"), ("vinaigrette", 0.8, "both"),
            ("grillsauce", 0.8, "de"), ("bbq sauce", 0.8, "en"),
            ("aioli", 0.8, "both"), ("honig", 0.6, "de"),
            ("honey", 0.6, "en"), ("sirup", 0.6, "de"),
            ("syrup", 0.6, "en"), ("ahornsirup", 0.8, "de"),
            ("maple syrup", 0.8, "en"), ("peanut butter", 0.9, "en"),
            ("erdnussbutter", 1.0, "de"), ("marmelade", 0.7, "de"),
            ("jam", 0.6, "en"),
        ],
    },
    "cat_pantry_spices": {
        "path": ["Pantry & Staples", "Spices & Seasoning"],
        "keywords": [
            ("salz", 0.8, "de"), ("salt", 0.7, "en"),
            ("pfeffer", 0.8, "de"), ("pepper", 0.6, "en"),
            ("gewurz", 0.5, "de"), ("spice", 0.4, "en"),
            ("paprika gewurz", 0.9, "de"), ("curry", 0.7, "both"),
            ("zimt", 0.8, "de"), ("cinnamon", 0.8, "en"),
            ("muskat", 0.8, "de"), ("oregano", 0.8, "both"),
            ("basilikum", 0.7, "de"), ("thymian", 0.7, "de"),
            ("rosmarin", 0.7, "de"), ("chili", 0.5, "both"),
            ("cayenne", 0.8, "both"), ("brühe", 0.7, "de"),
            ("bruehe", 0.7, "de"), ("bouillon", 0.8, "both"),
            ("fond", 0.5, "both"), ("knoblauch gewurz", 0.7, "de"),
            ("sugar", 0.6, "en"), ("powdered sugar", 0.8, "en"),
            ("icing sugar", 0.8, "en"), ("zucker", 0.7, "de"),
            ("puderzucker", 0.8, "de"), ("sweetener", 0.7, "en"),
            ("zuckerersatz", 0.8, "de"), ("flour", 0.6, "en"),
            ("mehl", 0.7, "de"), ("wheat flour", 0.7, "en"),
            ("weizenmehl", 0.8, "de"), ("spelled flour", 0.7, "en"),
            ("dinkelmehl", 0.8, "de"), ("baking powder", 0.7, "en"),
            ("backpulver", 0.8, "de"), ("yeast", 0.7, "en"),
            ("hefe", 0.7, "de"), ("vanilla sugar", 0.7, "en"),
            ("vanillezucker", 0.8, "de"),
        ],
    },
    "cat_pantry_canned": {
        "path": ["Pantry & Staples", "Canned & Jarred"],
        "keywords": [
            ("dose", 0.3, "de"), ("canned", 0.4, "en"),
            ("tomaten dose", 0.8, "de"), ("canned tomatoes", 0.8, "en"),
            ("bohnen dose", 0.8, "de"), ("canned beans", 0.8, "en"),
            ("mais dose", 0.7, "de"), ("canned corn", 0.7, "en"),
            ("linsen dose", 0.8, "de"), ("canned lentils", 0.8, "en"),
            ("suppe dose", 0.8, "de"), ("canned soup", 0.8, "en"),
            ("fertiggericht", 0.5, "de"), ("ready meal", 0.5, "en"),
        ],
    },

    # ═══════════ BEVERAGES ═══════════
    "cat_beverages_water": {
        "path": ["Beverages", "Water"],
        "keywords": [
            ("wasser", 0.7, "de"), ("water", 0.6, "en"),
            ("mineralwasser", 1.0, "de"), ("mineral water", 0.9, "en"),
            ("stilles wasser", 0.9, "de"), ("still water", 0.8, "en"),
            ("medium wasser", 0.8, "de"), ("säuerling", 0.8, "de"),
            ("voslauer", 0.8, "de"), ("romerquelle", 0.8, "de"),
            ("prebl", 0.8, "de"), ("aqua", 0.4, "both"),
            ("hipp baby mineralwasser", 0.9, "de"),
        ],
    },
    "cat_beverages_soft": {
        "path": ["Beverages", "Soft Drinks"],
        "keywords": [
            ("cola", 0.8, "both"), ("pepsi", 0.9, "both"),
            ("fanta", 0.9, "both"), ("sprite", 0.9, "both"),
            ("seven up", 0.9, "en"), ("almdudler", 0.9, "de"),
            ("limonade", 0.7, "de"), ("lemonade", 0.7, "en"),
            ("eistee", 0.8, "de"), ("iced tea", 0.8, "en"),
            ("red bull", 0.8, "both"), ("energy drink", 0.7, "en"),
            ("tonic water", 0.8, "en"), ("tonic", 0.6, "both"),
            ("bitter lemon", 0.8, "en"), ("ginger ale", 0.8, "en"),
            ("schweppes", 0.8, "both"), ("soda", 0.4, "en"),
            ("soft drink", 0.4, "en"),
        ],
    },
    "cat_beverages_juice": {
        "path": ["Beverages", "Juices"],
        "keywords": [
            ("saft", 0.6, "de"), ("juice", 0.6, "en"),
            ("apfelsaft", 0.9, "de"), ("apple juice", 0.8, "en"),
            ("orangensaft", 0.9, "de"), ("orange juice", 0.8, "en"),
            ("marille saft", 0.8, "de"), ("multivitamin", 0.6, "both"),
            ("nektar", 0.6, "both"), ("traubensaft", 0.9, "de"),
            ("grape juice", 0.8, "en"), ("cranberry", 0.7, "both"),
            ("smoothie", 0.8, "both"), ("direktsaft", 0.8, "de"),
            ("fruchtnektar", 0.8, "de"), ("mango pfirsich", 0.7, "de"),
        ],
    },
    "cat_beverages_beer": {
        "path": ["Beverages", "Beer"],
        "keywords": [
            ("bier", 0.8, "de"), ("beer", 0.7, "en"),
            ("ottakringer", 0.9, "de"), ("gosser", 0.9, "de"),
            ("stiegl", 0.9, "de"), ("zipfer", 0.9, "de"),
            ("pils", 0.7, "both"), ("märzen", 0.8, "de"),
            ("weizenbier", 0.9, "de"), ("wheat beer", 0.8, "en"),
            ("radler", 0.8, "de"), ("alkoholfrei", 0.4, "de"),
            ("alcohol free", 0.4, "en"), ("craft beer", 0.8, "en"),
            ("lager", 0.5, "en"), ("helles", 0.7, "de"),
            ("pilsner", 0.8, "en"), ("ipa", 0.6, "both"),
        ],
    },
    "cat_beverages_wine_spirits": {
        "path": ["Beverages", "Wine & Spirits"],
        "keywords": [
            ("wein", 0.7, "de"), ("wine", 0.7, "en"),
            ("grüner veltliner", 1.0, "de"), ("riesling", 0.9, "both"),
            ("zweigelt", 0.9, "de"), ("merlot", 0.8, "both"),
            ("cabernet", 0.8, "both"), ("chardonnay", 0.8, "both"),
            ("sauvignon", 0.8, "both"), ("prosecco", 0.9, "both"),
            ("sekt", 0.8, "de"), ("champagner", 0.8, "de"),
            ("aperol", 0.8, "both"), ("campari", 0.8, "both"),
            ("wodka", 0.8, "de"), ("vodka", 0.8, "en"),
            ("whisky", 0.8, "both"), ("rum", 0.7, "both"),
            ("gin", 0.7, "both"), ("schnaps", 0.8, "de"),
            ("grappa", 0.8, "both"), ("spritz", 0.5, "both"),
            ("st. laurent", 0.9, "de"), ("blaufrankisch", 0.9, "de"),
            ("blaufränkisch", 0.9, "de"), ("rose", 0.6, "both"),
            ("rose wine", 0.7, "en"), ("rosé", 0.7, "de"),
            ("kalk und schiefer", 0.5, "de"), ("heideboden", 0.6, "de"),
            ("pinot", 0.8, "both"), ("syrah", 0.8, "both"),
            ("tempranillo", 0.8, "both"), ("malbec", 0.8, "both"),
            ("sankt laurent", 0.9, "de"), ("gelber muskateller", 0.9, "de"),
            ("muskateller", 0.8, "de"), ("traminer", 0.8, "both"),
            ("weissburgunder", 0.9, "de"), ("weißburgunder", 0.9, "de"),
            ("pinot blanc", 0.8, "en"), ("rotwein", 0.8, "de"),
            ("weisswein", 0.8, "de"), ("red wine", 0.7, "en"),
            ("white wine", 0.7, "en"),
        ],
    },
    "cat_beverages_coffee_tea": {
        "path": ["Beverages", "Coffee & Tea"],
        "keywords": [
            ("kaffee", 0.8, "de"), ("coffee", 0.8, "en"),
            ("espresso", 0.9, "both"), ("cappuccino", 0.9, "both"),
            ("latte", 0.6, "both"), ("filterkaffee", 0.9, "de"),
            ("vollbohne", 0.8, "de"), ("whole bean", 0.8, "en"),
            ("tee", 0.7, "de"), ("tea", 0.7, "en"),
            ("pfefferminztee", 0.9, "de"), ("peppermint tea", 0.8, "en"),
            ("grüner tee", 0.9, "de"), ("green tea", 0.8, "en"),
            ("schwarztee", 0.9, "de"), ("black tea", 0.8, "en"),
            ("kamille", 0.7, "de"), ("chamomile", 0.7, "en"),
            ("früchtetee", 0.9, "de"), ("fruit tea", 0.8, "en"),
            ("nescafé", 0.7, "de"), ("nescafe", 0.7, "en"),
            ("3in1", 0.3, "both"), ("instant coffee", 0.7, "en"),
            ("hot chocolate", 0.7, "en"), ("kakao", 0.5, "de"),
        ],
    },

    # ═══════════ SNACKS & SWEETS ═══════════
    "cat_snacks_chocolate": {
        "path": ["Snacks & Sweets", "Chocolate"],
        "keywords": [
            ("schokolade", 0.9, "de"), ("chocolate", 0.8, "en"),
            ("milka", 0.8, "both"), ("lindt", 0.8, "both"),
            ("manner", 0.7, "de"), ("suchard", 0.8, "both"),
            ("ritter sport", 0.9, "both"), ("toblerone", 0.9, "both"),
            ("praline", 0.8, "both"), ("nougat", 0.8, "both"),
            ("weisse schokolade", 0.9, "de"), ("white chocolate", 0.8, "en"),
            ("zartbitter", 0.8, "de"), ("dark chocolate", 0.8, "en"),
            ("nesquik", 0.7, "both"), ("kaba", 0.8, "de"),
            ("nutella", 0.7, "both"), ("nutella ice cream", 0.5, "en"),
        ],
    },
    "cat_snacks_candy": {
        "path": ["Snacks & Sweets", "Candy & Gum"],
        "keywords": [
            ("gummibärchen", 1.0, "de"), ("gummibaerchen", 1.0, "de"),
            ("haribo", 0.9, "both"), ("bonbon", 0.8, "de"),
            ("lutscher", 0.8, "de"), ("kaubonbon", 0.9, "de"),
            ("kaugummi", 0.9, "de"), ("zuckerl", 0.9, "de"),
            ("traubenzucker", 0.8, "de"), ("glucose", 0.5, "both"),
            ("mars", 0.5, "both"), ("snickers", 0.9, "both"),
            ("twix", 0.9, "both"), ("kitkat", 0.9, "both"),
            ("kinder", 0.4, "both"),
        ],
    },
    "cat_snacks_chips": {
        "path": ["Snacks & Sweets", "Chips & Snacks"],
        "keywords": [
            ("chips", 0.8, "both"), ("pringles", 0.9, "both"),
            ("cracker", 0.7, "both"), ("popcorn", 0.8, "both"),
            ("erdnuss", 0.6, "de"), ("peanut", 0.5, "en"),
            ("nussmix", 0.8, "de"), ("nut mix", 0.7, "en"),
            ("studentenfutter", 0.9, "de"), ("trail mix", 0.8, "en"),
            ("cashew", 0.8, "both"), ("mandel", 0.5, "de"),
            ("almond", 0.5, "en"), ("walnuss", 0.6, "de"),
            ("walnut", 0.5, "en"), ("pretzel", 0.8, "both"),
            ("brezel", 0.8, "de"), ("chio", 0.7, "both"),
            ("lays", 0.8, "both"), ("paprika chips", 0.7, "both"),
        ],
    },
    "cat_snacks_protein": {
        "path": ["Snacks & Sweets", "Protein & Health Bars"],
        "keywords": [
            ("protein bar", 0.9, "en"), ("proteinriegel", 1.0, "de"),
            ("protein bar", 0.9, "en"), ("protein", 0.4, "both"),
            ("riegel", 0.4, "de"), ("bar", 0.3, "en"),
            ("energy bar", 0.7, "en"), ("müsliriegel", 0.9, "de"),
            ("cereal bar", 0.7, "en"),
        ],
    },

    # ═══════════ FROZEN ═══════════
    "cat_frozen_meals": {
        "path": ["Frozen", "Frozen Meals"],
        "keywords": [
            ("tiefkuhl", 0.6, "de"), ("tiefkühl", 0.6, "de"),
            ("frozen", 0.5, "en"), ("tk", 0.3, "de"),
            ("pizza", 0.7, "both"), ("tiefkuhlpizza", 1.0, "de"),
            ("frozen pizza", 0.8, "en"), ("lasagne tk", 0.8, "de"),
            ("schnitzel tk", 0.8, "de"), ("fertiggericht", 0.4, "de"),
            ("ready meal", 0.4, "en"), ("nugget", 0.6, "en"),
            ("nuggets", 0.6, "en"), ("dino nuggets", 0.8, "en"),
            ("chicken nuggets", 0.7, "en"), ("fish fingers", 0.8, "en"),
            ("fingers", 0.3, "en"), ("burger", 0.6, "en"),
            ("frozen fries", 0.7, "en"), ("pommes", 0.7, "de"),
            ("croquette", 0.7, "en"), ("croquettes", 0.7, "en"),
            ("kroketten", 0.8, "de"), ("rosti", 0.7, "en"),
            ("rösti", 0.7, "de"),
        ],
    },
    "cat_frozen_vegetables": {
        "path": ["Frozen", "Frozen Vegetables & Fruits"],
        "keywords": [
            ("tk gemuse", 0.9, "de"), ("tk gemüse", 0.9, "de"),
            ("tk obst", 0.8, "de"), ("frozen vegetables", 0.8, "en"),
            ("frozen fruit", 0.8, "en"), ("tiefkuhlbeeren", 0.9, "de"),
            ("frozen berries", 0.8, "en"), ("tiefkuhlspinat", 0.9, "de"),
            ("frozen spinach", 0.8, "en"),
        ],
    },
    "cat_frozen_icecream": {
        "path": ["Frozen", "Ice Cream"],
        "keywords": [
            ("eis", 0.6, "de"), ("ice cream", 0.9, "en"),
            ("speiseeis", 1.0, "de"), ("vanilleeis", 1.0, "de"),
            ("stracciatella", 0.8, "both"), ("magnum", 0.8, "both"),
            ("cornetto", 0.8, "both"), ("sorbet", 0.8, "both"),
            ("frozen yogurt", 0.8, "en"), ("glace", 0.7, "de"),
            ("schöller", 0.8, "de"), ("schoeller", 0.8, "de"),
            ("cioccolato", 0.7, "en"), ("gelato", 0.8, "both"),
            ("gelateria", 0.5, "both"),
        ],
    },

    # ═══════════ HOUSEHOLD & PERSONAL CARE ═══════════
    "cat_household_cleaning": {
        "path": ["Household", "Cleaning"],
        "keywords": [
            ("waschmittel", 1.0, "de"), ("detergent", 0.8, "en"),
            ("vollwaschmittel", 1.0, "de"), ("colorwaschmittel", 1.0, "de"),
            ("weichspuler", 0.9, "de"), ("weichspüler", 0.9, "de"),
            ("fabric softener", 0.8, "en"), ("spulmittel", 0.9, "de"),
            ("dish soap", 0.8, "en"), ("allzweckreiniger", 0.9, "de"),
            ("all purpose cleaner", 0.8, "en"), ("badreiniger", 0.8, "de"),
            ("bathroom cleaner", 0.8, "en"), ("klo", 0.4, "de"),
            ("wc reiniger", 0.8, "de"), ("toilet cleaner", 0.8, "en"),
            ("glasreiniger", 0.8, "de"), ("glass cleaner", 0.8, "en"),
            ("desinfektion", 0.7, "de"), ("disinfectant", 0.7, "en"),
            ("sponge", 0.7, "en"), ("sponges", 0.7, "en"),
            ("schwamm", 0.7, "de"), ("dishwashing", 0.6, "en"),
            ("dish soap", 0.7, "en"), ("dishwashing liquid", 0.7, "en"),
            ("geschirrspülmittel", 0.8, "de"), ("geschirrspuelmittel", 0.8, "de"),
            ("handkerchief", 0.7, "en"), ("handkerchiefs", 0.7, "en"),
            ("taschentücher", 0.8, "de"), ("taschentuecher", 0.8, "de"),
            ("citrus", 0.4, "en"), ("citrus fresh", 0.5, "en"),
        ],
    },
    "cat_household_paper": {
        "path": ["Household", "Paper & Disposables"],
        "keywords": [
            ("toilettenpapier", 1.0, "de"), ("toilet paper", 0.9, "en"),
            ("taschentuch", 0.8, "de"), ("tissue", 0.7, "en"),
            ("tempo", 0.6, "both"), ("kitchen roll", 0.8, "en"),
            ("kuchenrolle", 0.9, "de"), ("alufolie", 0.8, "de"),
            ("aluminum foil", 0.8, "en"), ("frischhaltefolie", 0.9, "de"),
            ("cling film", 0.8, "en"), ("mullsack", 0.8, "de"),
            ("müllsack", 0.8, "de"), ("trash bag", 0.8, "en"),
        ],
    },
    "cat_household_personal": {
        "path": ["Household", "Personal Care"],
        "keywords": [
            ("shampoo", 0.9, "both"), ("duschgel", 1.0, "de"),
            ("shower gel", 0.8, "en"), ("seife", 0.8, "de"),
            ("soap", 0.7, "en"), ("zahnpasta", 0.9, "de"),
            ("toothpaste", 0.8, "en"), ("zahnbürste", 0.9, "de"),
            ("toothbrush", 0.8, "en"), ("deodorant", 0.9, "both"),
            ("handcreme", 0.8, "de"), ("hand cream", 0.8, "en"),
            ("sonnencreme", 0.8, "de"), ("sunscreen", 0.8, "en"),
            ("bodylotion", 0.8, "both"), ("conditioner", 0.8, "en"),
            ("rasierer", 0.7, "de"), ("razor", 0.7, "en"),
            ("incontinence", 0.8, "en"), ("blasenschwäche", 0.8, "de"),
            ("blasenschwaeche", 0.8, "de"), ("incontinence pants", 0.8, "en"),
            ("adult diaper", 0.8, "en"), ("slip", 0.3, "en"),
        ],
    },
    "cat_health_supplements": {
        "path": ["Health & Wellness", "Vitamins & Supplements"],
        "keywords": [
            ("vitamin", 0.7, "both"), ("vitamine", 0.7, "de"),
            ("magnesium", 0.8, "both"), ("zink", 0.7, "de"),
            ("zinc", 0.7, "en"), ("calcium", 0.7, "both"),
            ("biotin", 0.7, "both"), ("eisen", 0.7, "de"),
            ("iron", 0.7, "en"), ("omega 3", 0.8, "both"),
            ("kieselerde", 0.7, "de"), ("brausetablette", 0.5, "de"),
            ("forte", 0.3, "both"), ("depot", 0.3, "both"),
            ("immun", 0.5, "de"), ("immune", 0.5, "en"),
            ("nahrungsergänzung", 0.8, "de"), ("supplement", 0.6, "en"),
            ("abtei", 0.5, "both"), ("doppelherz", 0.6, "both"),
        ],
    },

    # ═══════════ BABY & PETS ═══════════
    "cat_baby": {
        "path": ["Baby & Kids", "Baby Food & Care"],
        "keywords": [
            ("baby", 0.6, "both"), ("windel", 0.9, "de"),
            ("diaper", 0.8, "en"), ("diapers", 0.8, "en"),
            ("pampers", 0.8, "both"), ("babynahrung", 1.0, "de"),
            ("baby food", 0.9, "en"), ("brei", 0.4, "de"),
            ("milchnahrung", 0.9, "de"), ("formula", 0.7, "en"),
            ("pre milch", 0.7, "de"), ("folgemilch", 0.9, "de"),
            ("babybrei", 1.0, "de"), ("feuchttucher", 0.8, "de"),
            ("baby wipes", 0.8, "en"), ("hipp", 0.6, "both"),
        ],
    },
    "cat_pets": {
        "path": ["Pets", "Pet Food"],
        "keywords": [
            ("katzenfutter", 1.0, "de"), ("cat food", 0.9, "en"),
            ("hundfutter", 1.0, "de"), ("dog food", 0.9, "en"),
            ("whiskas", 0.9, "both"), ("felix", 0.7, "both"),
            ("royal canin", 0.9, "both"), ("pedigree", 0.9, "both"),
            ("purina", 0.7, "both"), ("tierfutter", 0.8, "de"),
            ("pet food", 0.8, "en"), ("hunde", 0.5, "de"),
            ("katzen", 0.5, "de"), ("haustier", 0.7, "de"),
            ("trockenfutter", 0.7, "de"), ("nassfutter", 0.7, "de"),
            ("dog treats", 0.7, "en"), ("katzenstreu", 0.8, "de"),
            ("cat litter", 0.7, "en"), ("hundeleckerli", 0.8, "de"),
        ],
    },
}

# ───────────────────────────────────────────────────────────────────────
# DE→EN TRANSLATION MAP for "both" keywords that are German-only words
# This allows matching English names too
# ───────────────────────────────────────────────────────────────────────

_DE_TO_EN = {
    "milch": "milk", "vollmilch": "whole milk", "frischmilch": "fresh milk",
    "heumilch": "hay milk", "biomilch": "organic milk",
    "haltbarmilch": "long-life milk", "buttermilch": "buttermilk",
    "sojamilch": "soy milk", "mandelmilch": "almond milk",
    "hafermilch": "oat milk", "dinkelmilch": "spelt milk",
    "kokosmilch": "coconut milk", "kakao milch": "cocoa milk",
    "schokoladenmilch": "chocolate milk", "trinkmilch": "drinking milk",
    "trinkjoghurt": "drink yogurt", "fruchtjoghurt": "fruit yogurt",
    "naturjoghurt": "natural yogurt", "milchreis": "rice pudding",
    "griechischer joghurt": "greek yogurt", "quarkspeise": "quark dessert",
    "quark speise": "quark dessert",
    "rahm": "cream", "sahne": "cream", "obers": "cream",
    "schlagsahne": "whipping cream", "kochsahne": "cooking cream",
    "schlagobers": "whipping cream", "saure sahne": "sour cream",
    "butter milch": "buttermilk",
    "frischkase": "cream cheese", "frischkäse": "cream cheese",
    "hirtenkase": "shepherd cheese", "hirtenkäse": "shepherd cheese",
    "schafskase": "sheep cheese", "schmelzkase": "processed cheese",
    "streichkase": "spreadable cheese", "grillkase": "grill cheese",
    "handkase": "hand cheese", "bergkase": "mountain cheese",
    "scheibenkase": "sliced cheese", "wurfelskase": "cheese cubes",
    "reibekase": "grated cheese", "parmesan gerieben": "grated parmesan",
    "blauschimmelkase": "blue cheese",
    "kartoffel": "potato", "erdapfel": "potato", "erdäpfel": "potato",
    "karotte": "carrot", "karotten": "carrots",
    "gurke": "cucumber", "zwiebel": "onion",
    "lauch": "leek", "porree": "leek",
    "spinat": "spinach", "kohl": "cabbage", "kraut": "cabbage",
    "kurbis": "pumpkin", "kürbis": "pumpkin",
    "gemuse": "vegetable", "gemüse": "vegetable",
    "champignon": "mushroom", "champignons": "mushrooms",
    "pilze": "mushrooms", "knoblauch": "garlic",
    "mais": "corn", "bohne": "bean", "linse": "lentil",
    "ingwer": "ginger", "rettich": "radish", "sellerie": "celery",
    "obst": "fruit", "apfel": "apple", "birne": "pear",
    "pfirsich": "peach", "aprikose": "apricot", "marille": "apricot",
    "pflaume": "plum", "kirsche": "cherry",
    "himbeere": "raspberry", "erdbeere": "strawberry",
    "blaubeere": "blueberry", "heidelbeere": "blueberry",
    "traube": "grape", "ananas": "pineapple",
    "wassermelone": "watermelon", "passionsfrucht": "passion fruit",
    "limette": "lime", "datteln": "dates", "beeren": "berries",
    "datteln ohne stein": "pitted dates",
    "frucht mix": "fruit mix", "granatapfel": "pomegranate",
    "lauchkrauter": "herb blend", "krauter": "herbs",
    "krautermix": "herb mix", "petersilie": "parsley",
    "schnittlauch": "chives", "minze": "mint", "koriander": "coriander",
    "salbei": "sage", "basilikum": "basil", "thymian": "thyme",
    "rosmarin": "rosemary",
    "hahnchen": "chicken", "haehnchen": "chicken", "hendl": "chicken",
    "putenbrust": "turkey breast", "pute": "turkey",
    "truthahn": "turkey", "keule": "drumstick",
    "hahnchenbrust": "chicken breast",
    "rind": "beef", "schwein": "pork", "steak": "steak",
    "schnitzel": "schnitzel", "gulasch": "goulash",
    "hackfleisch": "minced meat", "faschiertes": "minced meat",
    "geschnetzeltes": "sliced meat", "filet": "fillet",
    "roulade": "roulade", "schweinsbraten": "pork roast",
    "rostbraten": "roast beef",
    "wurstel": "sausage", "wurfstel": "sausage", "debreziner": "debreziner",
    "kasekrainer": "cheese sausage",
    "schinken": "ham", "speck": "bacon", "aufschnitt": "cold cuts",
    "extrawurst": "extra sausage", "landjager": "landjaeger",
    "landjäger": "landjaeger", "leberkase": "meatloaf",
    "leberkäse": "meatloaf", "wurstsalat": "sausage salad",
    "hering": "herring", "fischstabchen": "fish fingers",
    "fischfilet": "fish fillet", "fischstäbchen": "fish fingers",
    "brot": "bread", "weckerl": "roll", "semmel": "roll",
    "vollkornbrot": "whole grain bread", "weissbrot": "white bread",
    "weißbrot": "white bread", "schwarzbrot": "black bread",
    "grauerl": "brown roll", "toastbrot": "toast bread",
    "krustenbrot": "crust bread", "bauernbrot": "farmer bread",
    "landbrot": "country bread", "blatteteig": "puff pastry",
    "pizzateig": "pizza dough", "geback": "pastry",
    "kipferl": "crescent roll", "plunder": "danish pastry",
    "kuchen": "cake", "torte": "cake",
    "nudel": "noodle", "nudeln": "noodles",
    "spatzle": "spaetzle",
    "reis": "rice", "naturreis": "brown rice",
    "wildreis": "wild rice", "dinkel": "spelt",
    "haferflocken": "oat flakes", "polenta": "polenta",
    "grieß": "semolina", "gruß": "semolina",
    "olivenol": "olive oil", "sonnenblumenol": "sunflower oil",
    "rapswol": "rapeseed oil", "rapsoel": "rapeseed oil",
    "kurbiskernol": "pumpkin seed oil",
    "walnussol": "walnut oil", "ol": "oil",
    "essig": "vinegar", "apfelessig": "apple cider vinegar",
    "weinessig": "wine vinegar",
    "sauce": "sauce", "senf": "mustard", "sojasauce": "soy sauce",
    "tomatensauce": "tomato sauce", "salatdressing": "salad dressing",
    "grillsauce": "grill sauce", "honig": "honey",
    "sirup": "syrup", "ahornsirup": "maple syrup",
    "marmelade": "jam", "erdnussbutter": "peanut butter",
    "salz": "salt", "pfeffer": "pepper", "gewurz": "spice",
    "gewürz": "spice", "zimt": "cinnamon", "muskat": "nutmeg",
    "brühe": "broth", "bruehe": "broth",
    "knoblauch gewurz": "garlic spice", "paprika gewurz": "paprika spice",
    "dose": "can", "tomaten dose": "canned tomatoes",
    "bohnen dose": "canned beans", "mais dose": "canned corn",
    "linsen dose": "canned lentils", "suppe dose": "canned soup",
    "fertiggericht": "ready meal",
    "wasser": "water", "mineralwasser": "mineral water",
    "stilles wasser": "still water", "medium wasser": "medium water",
    "säuerling": "sparkling", "voslauer": "voslauer",
    "romerquelle": "roemerquelle", "hipp baby mineralwasser": "hipp baby water",
    "limonade": "lemonade", "eistee": "iced tea",
    "tonic water": "tonic water", "bitter lemon": "bitter lemon",
    "ginger ale": "ginger ale", "saft": "juice",
    "apfelsaft": "apple juice", "orangensaft": "orange juice",
    "marille saft": "apricot juice",
    "traubensaft": "grape juice", "direktsaft": "direct juice",
    "fruchtnektar": "fruit nectar", "mango pfirsich": "mango peach",
    "bier": "beer", "pils": "pils", "märzen": "maerzen",
    "weizenbier": "wheat beer", "radler": "radler",
    "alkoholfrei": "alcohol free",
    "wein": "wine", "grüner veltliner": "gruener veltliner",
    "zweigelt": "zweigelt", "sekt": "sparkling wine",
    "champagner": "champagne", "wodka": "vodka",
    "schnaps": "schnapps",
    "kaffee": "coffee", "filterkaffee": "filter coffee",
    "vollbohne": "whole bean", "tee": "tea",
    "pfefferminztee": "peppermint tea", "grüner tee": "green tea",
    "gruener tee": "green tea", "schwarztee": "black tea",
    "kamille": "chamomile", "früchtetee": "fruit tea",
    "fruechtetee": "fruit tea", "kakao": "cocoa",
    "schokolade": "chocolate", "weisse schokolade": "white chocolate",
    "zartbitter": "dark chocolate",
    "bonbon": "candy", "lutscher": "lollipop",
    "kaubonbon": "chewy candy", "kaugummi": "gum",
    "zuckerl": "candy", "traubenzucker": "glucose",
    "nussmix": "nut mix", "studentenfutter": "trail mix",
    "mandel": "almond", "walnuss": "walnut", "brezel": "pretzel",
    "protein": "protein", "riegel": "bar",
    "müsliriegel": "cereal bar",
    "tiefkuhl": "frozen", "tiefkühl": "frozen", "tk": "frozen",
    "lasagne tk": "frozen lasagna", "schnitzel tk": "frozen schnitzel",
    "tk gemuse": "frozen vegetables", "tk gemüse": "frozen vegetables",
    "tk obst": "frozen fruit", "tiefkuhlbeeren": "frozen berries",
    "tiefkuhlspinat": "frozen spinach",
    "eis": "ice cream", "speiseeis": "ice cream",
    "vanilleeis": "vanilla ice cream",
    "schöller": "schoeller", "schoeller": "schoeller",
    "glace": "ice cream",
    "waschmittel": "detergent", "vollwaschmittel": "full detergent",
    "colorwaschmittel": "color detergent",
    "weichspuler": "fabric softener", "weichspüler": "fabric softener",
    "spulmittel": "dish soap",
    "allzweckreiniger": "all purpose cleaner",
    "badreiniger": "bathroom cleaner",
    "klo": "toilet", "wc reiniger": "toilet cleaner",
    "glasreiniger": "glass cleaner",
    "desinfektion": "disinfectant",
    "taschentuch": "tissue", "kuchenrolle": "kitchen roll",
    "alufolie": "aluminum foil", "frischhaltefolie": "cling film",
    "mullsack": "trash bag", "müllsack": "trash bag",
    "duschgel": "shower gel", "seife": "soap",
    "zahnpasta": "toothpaste", "zahnbürste": "toothbrush",
    "handcreme": "hand cream", "sonnencreme": "sunscreen",
    "rasierer": "razor",
    "windel": "diaper", "babynahrung": "baby food",
    "brei": "porridge", "milchnahrung": "formula",
    "pre milch": "pre milk", "folgemilch": "follow-up milk",
    "babybrei": "baby porridge", "feuchttucher": "baby wipes",
    "katzenfutter": "cat food", "hundfutter": "dog food",
    "tierfutter": "pet food", "katzenstreu": "cat litter",
    "hundeleckerli": "dog treats", "katzenleckerli": "cat treats",
}

# Map: word → [(cat_id, weight), ...]
_WORD_INDEX = defaultdict(list)

for cat_id, cat_info in CATEGORIES.items():
    for keyword, weight, lang in cat_info["keywords"]:
        kw = keyword.lower().strip()
        _WORD_INDEX[kw].append((cat_id, weight, lang))
        # Umlaut variant
        kw_no_umlaut = kw.replace("ä", "a").replace("ö", "o").replace("ü", "u").replace("ß", "ss")
        if kw_no_umlaut != kw:
            _WORD_INDEX[kw_no_umlaut].append((cat_id, weight, lang))
        # English translation for "both" keywords
        if lang == "both" and kw in _DE_TO_EN:
            en_kw = _DE_TO_EN[kw].lower()
            _WORD_INDEX[en_kw].append((cat_id, weight, lang))
            for w in en_kw.split():
                if len(w) >= 2:
                    _WORD_INDEX[w].append((cat_id, weight * 0.5, lang))


# ───────────────────────────────────────────────────────────────────────
# CLASSIFIER
# ───────────────────────────────────────────────────────────────────────

def classify_product(name: str) -> dict:
    """
    Classify a product name into a hierarchical category.

    Returns:
      {
        "category_id": str | None,
        "category_path": list[str] | None,  # e.g. ["Dairy & Eggs", "Milk"]
        "confidence": float,                # 0.0–1.0
        "matched_keywords": list[str],
        "score": float,                     # raw score before normalization
        "all_scores": dict,                 # {cat_id: raw_score} for debugging
      }
    """
    if not name:
        return {
            "category_id": None, "category_path": None,
            "confidence": 0.0, "matched_keywords": [],
            "score": 0.0, "all_scores": {},
        }

    text = name.lower().strip()
    # Extract all words (2+ chars) for matching — supports accented chars (é, è, à, ñ, etc.)
    words = set(re.findall(r"[a-z0-9äöüßéèêëàáâãçñòóôõúùûüąćęłńśźż]+\b", text))

    # Create normalized versions of words (ä→a, ö→o, ü→u, ß→ss) for index lookup
    def _normalize(w):
        return w.replace("ä", "a").replace("ö", "o").replace("ü", "u").replace("ß", "ss").replace("é", "e").replace("è", "e").replace("ê", "e")

    all_words = set()
    for w in words:
        all_words.add(w)
        all_words.add(_normalize(w))

    scores = defaultdict(float)
    matched_keywords = defaultdict(list)

    # Single-word matching
    for word in all_words:
        if word in _WORD_INDEX:
            for cat_id, weight, lang in _WORD_INDEX[word]:
                scores[cat_id] += weight
                matched_keywords[cat_id].append(word)

    # Compound word substring matching — catches German compounds
    # e.g., "milch" inside "bauernmilch", "kase" inside "bergkase"
    _SHORT_KEYWORDS = [k for k in _WORD_INDEX if 3 <= len(k) <= 6]
    for word in all_words:
        for kw in _SHORT_KEYWORDS:
            if kw in word and kw not in matched_keywords.get("", []):
                for cat_id, weight, lang in _WORD_INDEX[kw]:
                    # Only match if keyword is at a word boundary (start or end of compound)
                    if word.startswith(kw) or word.endswith(kw):
                        scores[cat_id] += weight * 0.4  # Reduced weight for substring match
                        matched_keywords[cat_id].append(f"{kw}*")

    # Multi-word phrase matching (for compound keywords like "olive oil", "greek yogurt")
    for cat_id, cat_info in CATEGORIES.items():
        for keyword, weight, lang in cat_info["keywords"]:
            if len(keyword.split()) > 1:
                if keyword.lower() in text:
                    scores[cat_id] += weight * 1.5  # Bonus for phrase match
                    matched_keywords[cat_id].append(keyword)

    if not scores:
        return {
            "category_id": None, "category_path": None,
            "confidence": 0.0, "matched_keywords": [],
            "score": 0.0, "all_scores": {},
        }

    # Get the best category
    best_cat = max(scores, key=scores.get)
    best_score = scores[best_cat]

    # Normalise confidence: score of 2.5+ = 1.0 (very confident)
    confidence = min(1.0, best_score / 2.5)

    # Penalize if top 2 categories are very close (ambiguous)
    sorted_scores = sorted(scores.values(), reverse=True)
    if len(sorted_scores) >= 2:
        gap = sorted_scores[0] - sorted_scores[1]
        if gap < 1.0:
            confidence *= 0.7  # Reduce confidence if ambiguous

    return {
        "category_id": best_cat,
        "category_path": CATEGORIES[best_cat]["path"],
        "confidence": round(confidence, 3),
        "matched_keywords": list(set(matched_keywords[best_cat])),
        "score": round(best_score, 2),
        "all_scores": {k: round(v, 2) for k, v in sorted(scores.items(), key=lambda x: -x[1])[:5]},
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


def apply_categorisation(db=None, dry_run=False, limit=0, confidence_threshold=0.3):
    """Categorise all uncategorised products."""
    if db is None:
        db = get_db()

    query = {"$or": [
        {"categoryId": {"$in": [None, "cat_uncategorized", ""]}},
        {"categoryId": {"$exists": False}},
    ]}

    cursor = db.products.find(query)
    if limit > 0:
        cursor = cursor.limit(limit)

    docs = list(cursor)
    print(f"Found {len(docs):,} uncategorised products")

    results = {"total": len(docs), "categorised": 0, "review_queue": 0, "errors": 0}

    if dry_run:
        print("\n--- DRY RUN SAMPLES (first 40) ---")
        for i, doc in enumerate(docs[:40]):
            name = doc.get("name_de") or doc.get("name_en") or doc.get("name", "")
            cat_result = classify_product(name)
            if cat_result["confidence"] >= confidence_threshold:
                flag = "[AUTO]"
            else:
                flag = "[REVIEW]"
            path_str = " > ".join(cat_result["category_path"] or ["Uncategorised"])
            keywords = ", ".join(cat_result["matched_keywords"][:3])
            print(f"  [{i+1}] {name}")
            print(f"       {flag} → {path_str} (conf: {cat_result['confidence']:.2f}, keywords: {keywords})")
            if cat_result["all_scores"]:
                top3 = list(cat_result["all_scores"].items())[:3]
                print(f"       Top: {', '.join(f'{k}={v}' for k, v in top3)}")
            print()
        return results

    from pymongo import UpdateOne
    operations = []

    for doc in docs:
        try:
            name = doc.get("name_de") or doc.get("name_en") or doc.get("name", "")
            cat_result = classify_product(name)

            if cat_result["category_id"] and cat_result["confidence"] >= confidence_threshold:
                operations.append(UpdateOne(
                    {"_id": doc["_id"]},
                    {"$set": {
                        "categoryId": cat_result["category_id"],
                        "categoryPath": cat_result["category_path"],
                        "categoryConfidence": cat_result["confidence"],
                        "categoryKeywords": cat_result["matched_keywords"],
                        "updatedAt": __import__("datetime").datetime.utcnow(),
                    }}
                ))
                results["categorised"] += 1
            elif cat_result["category_id"]:
                operations.append(UpdateOne(
                    {"_id": doc["_id"]},
                    {"$set": {
                        "categoryId": "cat_review_queue",
                        "categoryPath": ["Review Queue"],
                        "categoryConfidence": cat_result["confidence"],
                        "categoryKeywords": cat_result["matched_keywords"],
                        "categorySuggestions": cat_result.get("all_scores", {}),
                        "updatedAt": __import__("datetime").datetime.utcnow(),
                    }}
                ))
                results["review_queue"] += 1
        except Exception:
            results["errors"] += 1

    batch_size = 2000
    for i in range(0, len(operations), batch_size):
        db.products.bulk_write(operations[i:i + batch_size], ordered=False)
        done = min(i + batch_size, len(operations))
        print(f"  Processed: {done:,}/{len(operations):,}")

    print(f"\nCategorised: {results['categorised']:,}  "
          f"Review queue: {results['review_queue']:,}  "
          f"Errors: {results['errors']:,}")
    return results


# ───────────────────────────────────────────────────────────────────────
# CLI
# ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Categorise products")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--threshold", type=float, default=0.3)
    args = parser.parse_args()

    result = apply_categorisation(dry_run=args.dry_run, limit=args.limit, confidence_threshold=args.threshold)
    print(f"\nResult: {result}")
