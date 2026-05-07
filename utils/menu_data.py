"""
═══════════════════════════════════════════════════════════════════════════
MEGA MENU DATA — PostgreSQL / SQLAlchemy
═══════════════════════════════════════════════════════════════════════════
Builds the hierarchical mega-menu data for the navigation bar.
"""

import time

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
}


def get_mega_menu():
    global _menu_cache
    if _menu_cache['data'] and time.time() - _menu_cache['ts'] < 60:
        return _menu_cache['data']

    try:
        from models.postgres_models import Category, Product

        # Build category tree from database
        categories = {}

        try:
            all_cats = Category.query.order_by(Category.name_en).all()

            # Build children map using integer IDs
            children_map = {}
            for c in all_cats:
                pid = c.parent_id  # integer or None
                children_map.setdefault(pid, []).append(c)

            # Grab Level 1 (Roots — parent_id is None)
            roots = children_map.get(None, [])

            for idx, root in enumerate(roots):
                root_name = root.name_en or root.name_de or 'Unknown'
                root_icon = root.icon or CAT_ICONS.get(root_name, 'bi-grid')

                subcats_dict = {}
                # Level 2 loop
                for l2 in children_map.get(root.id, []):
                    l2_name = l2.name_en or l2.name_de or 'Unknown'

                    # Level 3 loop
                    l3_list = []
                    for l3 in children_map.get(l2.id, []):
                        l3_name = l3.name_en or l3.name_de or 'Unknown'
                        l3_list.append(l3_name)

                    subcats_dict[l2_name] = l3_list

                categories[root_name] = {
                    'icon': root_icon,
                    'subcats': subcats_dict,
                    'count': 100 - idx
                }
        except Exception as e:
            print("Error building mega menu from DB:", e)
            # Fallback to hardcoded if DB fails
            categories = {}
            for idx, (cat_name, cat_data) in enumerate(TAXONOMY_TREE.items()):
                categories[cat_name] = {
                    'icon': cat_data['icon'],
                    'subcats': cat_data['subcats'],
                    'count': 100 - idx
                }

        # Brands aggregation
        brands = []
        try:
            from models.postgres_models import Brand
            brand_rows = Brand.query.order_by(Brand.name).limit(200).all()
            brands = [b.name or b.name_en for b in brand_rows if b.name or b.name_en]
        except Exception:
            brands = []

        # Build images map
        images = dict(DEFAULT_CAT_IMAGES)
        try:
            all_cat_rows = Category.query.all()
            for cat in all_cat_rows:
                if cat.name_en and cat.image_url:
                    images[cat.name_en] = cat.image_url
        except Exception:
            pass

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
