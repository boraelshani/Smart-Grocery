import pymongo, os, certifi, json
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv('/Users/drenbuqa/Documents/GitHub/Smart-Grocery/.env')
client = pymongo.MongoClient(os.environ['MONGO_URI'], tlsCAFile=certifi.where())
db = client['smart_grocery']

engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as c:
    # Get user mappings
    r = c.execute(text("SELECT email, id FROM users"))
    email_to_uid = {row[0]: row[1] for row in r}
    
    # Get product mappings
    r = c.execute(text("SELECT fingerprint, id FROM products"))
    fp_to_pid = {row[0]: row[1] for row in r}
    
    print("Migrating Favorites...")
    favs = db.favorites.find()
    inserted = 0
    for f in favs:
        email = f.get('user_email')
        prod_fp = f.get('product_id')
        uid = email_to_uid.get(email)
        pid = fp_to_pid.get(prod_fp)
        if uid and pid:
            try:
                c.execute(text("INSERT INTO favorites (user_id, product_id, created_at) VALUES (:u, :p, NOW()) ON CONFLICT DO NOTHING"), {'u': uid, 'p': pid})
                inserted += 1
            except: pass
    print(f"  Inserted {inserted} favorites.")
    
    print("Migrating Saved Recipes...")
    recipes = db.saved_recipes.find()
    inserted = 0
    for r in recipes:
        try:
            c.execute(text("""
                INSERT INTO saved_recipes 
                (user_email, title, ingredients, instructions, total_items, matched_items, total_price, created_at)
                VALUES (:email, :title, :ing, :ins, :ti, :mi, :tp, NOW())
            """), {
                'email': r.get('user_email'),
                'title': r.get('title'),
                'ing': json.dumps(r.get('ingredients', [])),
                'ins': json.dumps(r.get('instructions', [])),
                'ti': r.get('total_items', 0),
                'mi': r.get('matched_items', 0),
                'tp': float(r.get('total_price', 0))
            })
            inserted += 1
        except: pass
    print(f"  Inserted {inserted} saved recipes.")
    
    print("Migrating Public Lists...")
    lists = db.public_lists.find()
    inserted = 0
    for l in lists:
        try:
            c.execute(text("""
                INSERT INTO public_lists (list_id, name, items, created_at)
                VALUES (:lid, :name, :items, NOW())
            """), {
                'lid': l.get('list_id'),
                'name': l.get('name'),
                'items': json.dumps(l.get('items', []))
            })
            inserted += 1
        except: pass
    print(f"  Inserted {inserted} public lists.")
    
    c.commit()
    print("Migration complete!")
