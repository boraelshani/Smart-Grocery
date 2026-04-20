import time
from utils.db import mongo

_menu_cache = {'data': None, 'ts': 0}

# Stunning fallback/category images mapping
DEFAULT_CAT_IMAGES = {
    'Produce': 'https://images.unsplash.com/photo-1610832958506-aa56368176cf?q=80&w=300&auto=format&fit=crop',
    'Meat': 'https://images.unsplash.com/photo-1607623814075-e51df1bdfc82?q=80&w=300&auto=format&fit=crop',
    'Dairy': 'https://images.unsplash.com/photo-1628206126315-bd2903bc3983?q=80&w=300&auto=format&fit=crop',
    'Pantry': 'https://images.unsplash.com/photo-1613256038133-eef21eb79124?q=80&w=300&auto=format&fit=crop',
    'Frozen': 'https://images.unsplash.com/photo-1558500249-1e3d64bcade6?q=80&w=300&auto=format&fit=crop',
    'Bakery': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?q=80&w=300&auto=format&fit=crop',
    'Snacks': 'https://images.unsplash.com/photo-1599490659213-e2b9527bd087?q=80&w=300&auto=format&fit=crop',
    'Beverages': 'https://images.unsplash.com/photo-1556881180-2a74c4361b2d?q=80&w=300&auto=format&fit=crop',
    'Household': 'https://images.unsplash.com/photo-1585802115132-ee19bd5273cb?q=80&w=300&auto=format&fit=crop',
    
    # Precise Subcategory L1 Splashes
    'Fruits': 'https://images.unsplash.com/photo-1610832958506-aa56368176cf?q=80&w=400&auto=format&fit=crop',
    'Vegetables': 'https://images.unsplash.com/photo-1566385101042-1a0aa0c1268c?q=80&w=400&auto=format&fit=crop',
    'Poultry': 'https://images.unsplash.com/photo-1587595431973-160d0d94add1?q=80&w=400&auto=format&fit=crop',
    'Beef': 'https://images.unsplash.com/photo-1603048297172-c92544798d5e?q=80&w=400&auto=format&fit=crop',
    'Pork': 'https://images.unsplash.com/photo-1602414316365-d41adc3007eb?q=80&w=400&auto=format&fit=crop',
    'Milk': 'https://images.unsplash.com/photo-1563636619391-4c17b3d3ce16?q=80&w=400&auto=format&fit=crop',
    'Cheese': 'https://images.unsplash.com/photo-1486297678162-eb2a19b0a32d?q=80&w=400&auto=format&fit=crop',
    'Yogurt': 'https://images.unsplash.com/photo-1563729784400-da1bc57c91cf?q=80&w=400&auto=format&fit=crop',
    'Breakfast': 'https://images.unsplash.com/photo-1533089860892-a7c6f0a88666?q=80&w=400&auto=format&fit=crop',
    'Fruit': 'https://images.unsplash.com/photo-1610832958506-aa56368176cf?q=80&w=400&auto=format&fit=crop',

    # Extensive Mapping for deep SubCategories to ensure every block has a stunning contextual image
    'Apples': 'https://images.unsplash.com/photo-1560806887-1e4cd0b6fac6?q=80&w=400&auto=format&fit=crop',
    'Bananas': 'https://images.unsplash.com/photo-1571501679680-de32f1e7aad4?q=80&w=400&auto=format&fit=crop',
    'Berries': 'https://images.unsplash.com/photo-1563805042-7684c8a9e9cf?q=80&w=400&auto=format&fit=crop',
    'Grapes': 'https://images.unsplash.com/photo-1537640538966-79f369143f8f?q=80&w=400&auto=format&fit=crop',
    'Oranges': 'https://images.unsplash.com/photo-1582982855140-5cb0f9afffb9?q=80&w=400&auto=format&fit=crop',
    'Citrus': 'https://images.unsplash.com/photo-1611003463870-761e3d061730?q=80&w=400&auto=format&fit=crop',
    'Melons': 'https://images.unsplash.com/photo-1587310574045-8f6bca4a544a?q=80&w=400&auto=format&fit=crop',
    'Tomatoes': 'https://images.unsplash.com/photo-1592924357228-91a4daadcfea?q=80&w=400&auto=format&fit=crop',
    'Potatoes': 'https://images.unsplash.com/photo-1518977673343-a4a0f8b13689?q=80&w=400&auto=format&fit=crop',
    'Onions': 'https://images.unsplash.com/photo-1618512496248-a07ce83aa8cb?q=80&w=400&auto=format&fit=crop',
    'Leafy Greens': 'https://images.unsplash.com/photo-1576045057995-568f588f82fb?q=80&w=400&auto=format&fit=crop',
    'Peppers': 'https://images.unsplash.com/photo-1563565375-f3fdfdbefa8a?q=80&w=400&auto=format&fit=crop',
    'Root Vegetables': 'https://images.unsplash.com/photo-1590868309235-ea34bed7bd7f?q=80&w=400&auto=format&fit=crop',
    'Whole Milk': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?q=80&w=400&auto=format&fit=crop',
    'Oat Milk': 'https://images.unsplash.com/photo-1600271886742-f049cd451bba?q=80&w=400&auto=format&fit=crop',
    'Almond Milk': 'https://images.unsplash.com/photo-1615467008154-7264a7c1cd8f?q=80&w=400&auto=format&fit=crop',
    'Cheddar': 'https://images.unsplash.com/photo-1618012658514-6663edfa31a4?q=80&w=400&auto=format&fit=crop',
    'Cream Cheese': 'https://images.unsplash.com/photo-1634735518290-db0e7f7ce11e?q=80&w=400&auto=format&fit=crop',
    'Greek Yogurt': 'https://images.unsplash.com/photo-1488477181946-6428a0291777?q=80&w=400&auto=format&fit=crop',
    'Chicken': 'https://images.unsplash.com/photo-1604503468506-a8da13d82791?q=80&w=400&auto=format&fit=crop',
    'Ground Beef': 'https://images.unsplash.com/photo-1588168333986-5078d3ae3976?q=80&w=400&auto=format&fit=crop',
    'Bacon': 'https://images.unsplash.com/photo-1528607929212-2636ec44253e?q=80&w=400&auto=format&fit=crop',

}
DEFAULT_SUBCAT_IMAGE = 'https://images.unsplash.com/photo-1542838132-92c53300491e?q=80&w=200&auto=format&fit=crop'

# Fallback icons for navigation
CAT_ICONS = {
    'Produce': 'bi-apple', 'Meat': 'bi-egg-fried', 'Dairy': 'bi-Cup',
    'Pantry': 'bi-basket-fill', 'Frozen': 'bi-snow', 'Bakery': 'bi-cupcake',
    'Snacks': 'bi-cookie', 'Beverages': 'bi-cup-straw', 'Household': 'bi-house-heart',
    'Baby food': 'bi-cart', 'Fast Food & To Go': 'bi-truck'
}


TAXONOMY_TREE = {
    "Fruits & Vegetables": {
        "icon": "bi-apple",
        "subcats": {
            "Fresh Fruits": ["Berries", "Citrus", "Melons", "Stone Fruits", "Tropical", "Apples & Pears", "Grapes & Bananas"],
            "Fresh Vegetables": ["Leafy Greens", "Root Vegetables", "Salad Kits", "Cooking Vegetables", "Onions & Garlic", "Mushrooms"],
            "Fresh Herbs": ["Basil", "Cilantro", "Mint", "Parsley", "Rosemary", "Thyme"],
            "Prepared Produce": ["Cut Fruit", "Veggie Trays", "Stir-fry Mix", "Salsa-ready"]
        }
    },
    "Meat & Seafood": {
        "icon": "bi-egg-fried",
        "subcats": {
            "Fresh Meat": ["Beef", "Pork", "Lamb", "Veal", "Ground Meat"],
            "Poultry": ["Whole Chicken", "Chicken Breasts", "Chicken Thighs", "Turkey", "Ground Poultry"],
            "Seafood": ["Fresh Fish", "Frozen Fish", "Shellfish", "Shrimp", "Crab", "Canned Seafood"],
            "Deli Meat": ["Turkey Breast", "Ham", "Roast Beef", "Salami", "Bologna", "Pepperoni"],
            "Processed Meat": ["Sausages", "Hot Dogs", "Bacon", "Chorizo", "Meatballs"]
        }
    },
    "Dairy & Eggs": {
        "icon": "bi-Cup",
        "subcats": {
            "Milk": ["Whole Milk", "2% Milk", "Skim Milk", "Plant-based Milk", "Lactose-free"],
            "Cheese": ["Block Cheese", "Shredded Cheese", "Sliced Cheese", "Cream Cheese", "Cottage Cheese", "Parmesan", "Mozzarella"],
            "Yogurt": ["Greek Yogurt", "Regular Yogurt", "Drinkable Yogurt", "Plant-based Yogurt"],
            "Butter & Margarine": ["Salted Butter", "Unsalted Butter", "Plant-based Butter", "Spreads"],
            "Eggs": ["Large Eggs", "Extra Large Eggs", "Cage-free", "Organic", "Egg Whites"],
            "Cream & Milk Alternatives": ["Heavy Cream", "Half & Half", "Sour Cream", "Whipped Cream", "Non-dairy Creamer"]
        }
    },
    "Pantry Staples": {
        "icon": "bi-basket-fill",
        "subcats": {
            "Baking": ["Flour", "Sugar", "Brown Sugar", "Baking Soda", "Baking Powder", "Yeast", "Cocoa Powder"],
            "Oils & Vinegars": ["Olive Oil", "Vegetable Oil", "Coconut Oil", "Balsamic Vinegar", "White Vinegar", "Apple Cider Vinegar"],
            "Spices & Seasonings": ["Salt", "Black Pepper", "Garlic Powder", "Onion Powder", "Paprika", "Cinnamon", "Oregano", "Mixed Spices"],
            "Sauces & Condiments": ["Ketchup", "Mustard", "Mayonnaise", "Hot Sauce", "Soy Sauce", "BBQ Sauce", "Salad Dressing", "Pasta Sauce"],
            "Canned Goods": ["Canned Vegetables", "Canned Fruits", "Canned Beans", "Canned Tomatoes", "Canned Soup", "Canned Broth"],
            "Pasta, Rice & Grains": ["Dry Pasta", "Rice", "Quinoa", "Oats", "Couscous", "Lentils", "Dried Beans"],
            "Cooking & Baking Mixes": ["Pancake Mix", "Cake Mix", "Bread Mix", "Gravy Mix", "Seasoning Packets"]
        }
    },
    "Beverages": {
        "icon": "bi-cup-straw",
        "subcats": {
            "Water": ["Bottled Water", "Sparkling Water", "Flavored Water", "Gallon Water"],
            "Soft Drinks & Soda": ["Cola", "Lemon-lime", "Root Beer", "Ginger Ale", "Diet Soda"],
            "Juice": ["Orange Juice", "Apple Juice", "Cranberry Juice", "Grape Juice", "Vegetable Juice", "Juice Blends"],
            "Coffee": ["Ground Coffee", "Whole Bean Coffee", "Instant Coffee", "Decaf", "Coffee Pods"],
            "Tea": ["Black Tea", "Green Tea", "Herbal Tea", "Iced Tea", "Tea Bags", "Loose Leaf"],
            "Sports & Energy Drinks": ["Gatorade", "Powerade", "Red Bull", "Monster", "Energy Shots", "Electrolyte Water"],
            "Milk Alternatives": ["Almond Milk", "Oat Milk", "Soy Milk", "Coconut Milk"]
        }
    },
    "Snacks & Sweets": {
        "icon": "bi-cookie",
        "subcats": {
            "Chips & Crisps": ["Potato Chips", "Tortilla Chips", "Veggie Chips", "Pita Chips", "Popcorn"],
            "Cookies & Biscuits": ["Chocolate Chip", "Sandwich Cookies", "Butter Cookies", "Biscotti", "Graham Crackers"],
            "Candy & Chocolate": ["Chocolate Bars", "Gummy Candy", "Hard Candy", "Mints", "Licorice", "Seasonal Candy"],
            "Crackers & Rice Cakes": ["Saltines", "Ritz-style", "Whole Grain Crackers", "Rice Cakes", "Cheese Crackers"],
            "Nuts & Trail Mix": ["Peanuts", "Almond", "Cashews", "Walnuts", "Mixed Nuts", "Trail Mix", "Dried Fruit"],
            "Granola & Snack Bars": ["Granola Bars", "Protein Bars", "Cereal Bars", "Fruit Bars", "Rice Krispie Treats"],
            "Baked Goods": ["Muffins", "Doughnuts", "Brownies", "Pastries", "Pound Cake", "Loaf Cakes"]
        }
    },
    "Frozen Foods": {
        "icon": "bi-snow",
        "subcats": {
            "Frozen Vegetables": ["Mixed Vegetables", "Broccoli", "Spinach", "Peas & Carrots", "Stir-fry Blends"],
            "Frozen Fruits": ["Berries", "Mango", "Peaches", "Mixed Fruit", "Smoothie Packs"],
            "Frozen Meals": ["TV Dinners", "Frozen Pizza", "Frozen Burritos", "Frozen Bowls"],
            "Frozen Meat & Seafood": ["Frozen Chicken", "Frozen Fish Fillets", "Frozen Shrimp", "Frozen Burgers"],
            "Frozen Snacks": ["Frozen French Fries", "Onion Rings", "Mozzarella Sticks", "Pizza Rolls", "Frozen Appetizers"],
            "Ice Cream & Desserts": ["Ice Cream", "Sorbet", "Frozen Yogurt", "Ice Cream Sandwiches", "Popsicles", "Frozen Pie"]
        }
    },
    "Bakery & Bread": {
        "icon": "bi-cupcake",
        "subcats": {
            "Fresh Bread": ["White Bread", "Wheat Bread", "Sourdough", "Rye Bread", "Multigrain"],
            "Buns & Rolls": ["Hamburger Buns", "Hot Dog Buns", "Dinner Rolls", "Sub Rolls", "Croissants"],
            "Bagels & English Muffins": ["Plain Bagels", "Everything Bagels", "Cinnamon Raisin", "English Muffins"],
            "Tortillas & Wraps": ["Flour Tortillas", "Corn Tortillas", "Whole Wheat Wraps", "Lettuce Wraps"],
            "Pastries & Donuts": ["Fresh Donuts", "Muffins", "Croissants", "Danishes", "Cinnamon Rolls"],
            "In-store Bakery": ["Cakes", "Pies", "Cookies", "Cupcakes", "Brownies"]
        }
    },
    "Household & Cleaning": {
        "icon": "bi-house-heart",
        "subcats": {
            "Laundry": ["Laundry Detergent", "Fabric Softener", "Stain Removers", "Dryer Sheets"],
            "Cleaning Supplies": ["All-purpose Cleaner", "Glass Cleaner", "Bathroom Cleaner", "Disinfectant Spray"],
            "Dish Soap & Dishwasher": ["Dish Soap", "Dishwasher Detergent", "Rinse Aid", "Dishwasher Pods"],
            "Trash Bags & Storage": ["Trash Bags", "Zipper Bags", "Food Storage Containers", "Aluminum Foil", "Plastic Wrap"],
            "Paper Products": ["Paper Towels", "Toilet Paper", "Napkins", "Paper Plates", "Paper Cups"],
            "Air Fresheners": ["Sprays", "Plug-ins", "Candles", "Gel Beads", "Car Air Fresheners"]
        }
    },
    "Personal Care & Health": {
        "icon": "bi-heart-pulse",
        "subcats": {
            "Bath & Body": ["Body Wash", "Bar Soap", "Hand Soap", "Lotion", "Shampoo", "Conditioner"],
            "Oral Care": ["Toothpaste", "Toothbrushes", "Mouthwash", "Dental Floss", "Whitening Strips"],
            "Shaving & Grooming": ["Razors", "Razor Blades", "Shaving Cream", "Aftershave", "Trimmers"],
            "Feminine Care": ["Pads", "Tampons", "Liners", "Menstrual Cups", "Wipes"],
            "First Aid": ["Bandages", "Antiseptic", "Pain Relievers", "Cold Medicine", "Thermometers"],
            "Vitamins & Supplements": ["Multivitamins", "Vitamin C", "Vitamin D", "Protein Powder", "Probiotics"]
        }
    },
    "Baby & Kids": {
        "icon": "bi-cart",
        "subcats": {
            "Baby Food": ["Jarred Purees", "Pouch Purees", "Baby Cereal", "Teething Crackers", "Baby Snacks"],
            "Baby Formula": ["Powder Formula", "Liquid Concentrate", "Ready-to-Feed", "Toddler Formula"],
            "Diapers & Wipes": ["Diapers", "Pull-ups", "Baby Wipes", "Diaper Cream"],
            "Baby Drinks": ["Juice for Babies", "Water for Babies", "Electrolyte Solution"]
        }
    },
    "Pet Supplies": {
        "icon": "bi-github",
        "subcats": {
            "Dog Food": ["Dry Dog Food", "Wet Dog Food", "Dog Treats", "Dog Toppers"],
            "Cat Food": ["Dry Cat Food", "Wet Cat Food", "Cat Treats", "Cat Toppers"],
            "Pet Supplies": ["Cat Litter", "Pet Beds", "Pet Bowls", "Leashes", "Toys", "Poop Bags"]
        }
    },
    "International & Specialty": {
        "icon": "bi-globe",
        "subcats": {
            "Asian": ["Soy Sauce", "Rice Noodles", "Panko", "Curry Paste", "Coconut Milk", "Sriracha"],
            "Mexican": ["Tortillas", "Salsa", "Taco Seasoning", "Refried Beans", "Queso Fresco", "Hot Sauce"],
            "Italian": ["Pasta", "Pasta Sauce", "Olive Oil", "Balsamic Vinegar", "Parmesan", "Sun-dried Tomatoes"],
            "Indian": ["Basmati Rice", "Garam Masala", "Turmeric", "Cumin", "Curry Powder", "Ghee", "Naan"],
            "Mediterranean": ["Hummus", "Tahini", "Pita Bread", "Feta Cheese", "Olives", "Tzatziki"],
            "Organic & Natural": ["Organic produce", "Organic meat", "Gluten-free", "Keto-friendly", "Vegan"]
        }
    },
    "Alcohol": {
        "icon": "bi-cup-glass",
        "subcats": {
            "Beer": ["Lager", "IPA", "Stout", "Ale", "Non-alcoholic Beer", "Craft Beer"],
            "Wine": ["Red Wine", "White Wine", "Rosé", "Sparkling Wine", "Boxed Wine"],
            "Spirits": ["Vodka", "Whiskey", "Rum", "Gin", "Tequila", "Liqueurs", "Mixers"],
            "Hard Seltzer & Cider": ["Hard Seltzer", "Hard Cider", "Malt Beverages"]
        }
    }
}

def get_mega_menu():
    global _menu_cache
    import time
    if _menu_cache['data'] and time.time() - _menu_cache['ts'] < 3600:
        return _menu_cache['data']
        
    try:
        from utils.db import mongo
        
        categories = {}
        for idx, (cat_name, cat_data) in enumerate(TAXONOMY_TREE.items()):
            categories[cat_name] = {
                'icon': cat_data['icon'],
                'subcats': cat_data['subcats'],
                'count': 100 - idx  # Maintain fixed sorting priority exactly as defined
            }

        # 2. Brands aggregation -> just get all brands
        brands_pipe = [
            {"$match": {"brand": {"$ne": None, "$ne": ""}}},
            {"$group": {"_id": "$brand", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        try:
            brands_raw = list(mongo.db.products.aggregate(brands_pipe))
            brands = [b['_id'] for b in brands_raw if b['_id']]
        except:
            brands = []

        # 3. Dynamically fetch images from mongo.db.categories
        images = dict(DEFAULT_CAT_IMAGES)  # Start with fallback defaults
        try:
            category_docs = mongo.db.categories.find({})
            for doc in category_docs:
                if doc.get('name_en') and doc.get('imageUrl'):
                    images[doc['name_en']] = doc['imageUrl']
        except:
            pass  # Keep defaults if fetch fails

        data = {
            "categories": categories,
            "brands": brands,
            "images": images,
            "fallback_image": DEFAULT_SUBCAT_IMAGE
        }
        _menu_cache['data'] = data
        _menu_cache['ts'] = time.time()
        return data
    except Exception as e:
        print("Error fetching mega menu data:", e)
        return {"categories": {}, "brands": [], "images": {}, "fallback_image": ""}
