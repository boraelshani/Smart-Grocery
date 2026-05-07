import os
import json
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv('/Users/drenbuqa/Documents/GitHub/Smart-Grocery/.env')
engine = create_engine(os.environ['DATABASE_URL'])

# 1. Define our roots
ROOTS = {
    'Produce': {'icon': 'bi-apple', 'image': 'https://images.unsplash.com/photo-1610832958506-aa56368176cf'},
    'Meat & Seafood': {'icon': 'bi-egg-fried', 'image': 'https://images.unsplash.com/photo-1607623814075-e51df1bdfc82'},
    'Dairy & Eggs': {'icon': 'bi-cup-straw', 'image': 'https://images.unsplash.com/photo-1628206126315-bd2903bc3983'},
    'Bakery': {'icon': 'bi-shop', 'image': 'https://images.unsplash.com/photo-1509440159596-0249088772ff'},
    'Pantry': {'icon': 'bi-basket', 'image': 'https://images.unsplash.com/photo-1613256038133-eef21eb79124'},
    'Frozen': {'icon': 'bi-snow', 'image': 'https://images.unsplash.com/photo-1558500249-1e3d64bcade6'},
    'Beverages': {'icon': 'bi-cup', 'image': 'https://images.unsplash.com/photo-1556881180-2a74c4361b2d'},
    'Snacks & Sweets': {'icon': 'bi-cookie', 'image': 'https://images.unsplash.com/photo-1599490659213-e2b9527bd087'},
    'Household & Personal': {'icon': 'bi-house', 'image': 'https://images.unsplash.com/photo-1585802115132-ee19bd5273cb'},
    'Baby & Pet': {'icon': 'bi-heart', 'image': 'https://images.unsplash.com/photo-1516627145497-ae6968895b74'}
}

def guess_category(prods_text):
    text = prods_text.lower()
    if any(w in text for w in ['apfel', 'banane', 'gemüse', 'salat', 'kartoffel', 'tomate', 'obst', 'erdbeere']):
        return 'Produce', 'Fresh Produce', 'Obst & Gemüse'
    elif any(w in text for w in ['fleisch', 'rind', 'schwein', 'huhn', 'lachs', 'fisch', 'wurst', 'salami']):
        return 'Meat & Seafood', 'Meat & Seafood', 'Fleisch & Fisch'
    elif any(w in text for w in ['milch', 'käse', 'joghurt', 'butter', 'sahne', 'ei', 'eier']):
        return 'Dairy & Eggs', 'Dairy & Eggs', 'Milchprodukte & Eier'
    elif any(w in text for w in ['brot', 'semmel', 'kuchen', 'torte', 'gebäck']):
        return 'Bakery', 'Bakery', 'Bäckerei'
    elif any(w in text for w in ['nudeln', 'reis', 'mehl', 'zucker', 'öl', 'essig', 'gewürz', 'suppe', 'konserve', 'sauce']):
        return 'Pantry', 'Pantry & Staples', 'Vorrat & Kochen'
    elif any(w in text for w in ['tiefkühl', 'eis', 'pizza', 'pommes']):
        return 'Frozen', 'Frozen Foods', 'Tiefkühl'
    elif any(w in text for w in ['wasser', 'saft', 'cola', 'bier', 'wein', 'kaffee', 'tee']):
        return 'Beverages', 'Beverages', 'Getränke'
    elif any(w in text for w in ['schoko', 'chips', 'keks', 'snack', 'süß', 'gummibärchen']):
        return 'Snacks & Sweets', 'Snacks & Sweets', 'Snacks & Süßigkeiten'
    elif any(w in text for w in ['wasch', 'putz', 'reiniger', 'klopapier', 'shampoo', 'seife', 'deo']):
        return 'Household & Personal', 'Household', 'Haushalt & Pflege'
    elif any(w in text for w in ['baby', 'windel', 'hund', 'katze', 'tier']):
        return 'Baby & Pet', 'Baby & Pet', 'Baby & Tier'
    else:
        return 'Pantry', 'Groceries', 'Lebensmittel'

with engine.connect() as c:
    # Insert roots
    root_ids = {}
    for r_name, r_data in ROOTS.items():
        res = c.execute(text("INSERT INTO categories (slug, name_en, name_de, level, icon, image_url) VALUES (:s, :n, :n, 1, :i, :img) ON CONFLICT (slug) DO UPDATE SET name_en=EXCLUDED.name_en RETURNING id"), 
            {'s': r_name.lower().replace(' ', '-'), 'n': r_name, 'i': r_data['icon'], 'img': r_data['image']})
        root_ids[r_name] = res.scalar()
    
    # Process the 126 raw categories
    r = c.execute(text("SELECT id FROM categories WHERE name_en=slug OR name_en ~ '^[0-9a-f]+$'"))
    cats = [row[0] for row in r]
    
    for cat_id in cats:
        prods = c.execute(text(f"SELECT name_de FROM products WHERE category_id={cat_id} LIMIT 10"))
        prod_names = " ".join([p[0] for p in prods])
        
        root_name, sub_en, sub_de = guess_category(prod_names)
        
        c.execute(text("""
            UPDATE categories 
            SET name_en=:en, name_de=:de, parent_id=:pid, level=2
            WHERE id=:id
        """), {
            'en': sub_en,
            'de': sub_de,
            'pid': root_ids[root_name],
            'id': cat_id
        })
    c.commit()
    print("Categories updated successfully!")
