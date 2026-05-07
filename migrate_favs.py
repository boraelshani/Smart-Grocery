import pymongo, os, certifi
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv('/Users/drenbuqa/Documents/GitHub/Smart-Grocery/.env')
client = pymongo.MongoClient(os.environ['MONGO_URI'], tlsCAFile=certifi.where())
db = client['smart_grocery']
engine = create_engine(os.environ['DATABASE_URL'])

with engine.connect() as c:
    r = c.execute(text("SELECT email, id FROM users"))
    email_to_uid = {row[0]: row[1] for row in r}
    
    favs = list(db.favorites.find())
    inserted = 0
    for f in favs:
        email = f.get('user_email')
        name = f.get('product_name')
        uid = email_to_uid.get(email)
        if not uid or not name: continue
        
        # Find product by name
        r = c.execute(text("SELECT id FROM products WHERE name_de ILIKE :n LIMIT 1"), {'n': f"%{name}%"})
        pid = r.scalar()
        if pid:
            try:
                c.execute(text("INSERT INTO favorites (user_id, product_id, created_at) VALUES (:u, :p, NOW()) ON CONFLICT DO NOTHING"), {'u': uid, 'p': pid})
                inserted += 1
            except: pass
    c.commit()
    print(f"Inserted {inserted} favorites by name match.")
