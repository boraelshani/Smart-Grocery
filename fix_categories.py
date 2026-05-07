import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv('/Users/drenbuqa/Documents/GitHub/Smart-Grocery/.env')
engine = create_engine(os.environ['DATABASE_URL'])
genai.configure(api_key=os.environ['GEMINI_API_KEY'])
model = genai.GenerativeModel('gemini-1.5-flash')

with engine.connect() as c:
    # 1. Fetch the 126 categories and sample products
    r = c.execute(text("SELECT id, slug FROM categories WHERE name_en=slug OR name_en ~ '^[0-9a-f]+$'"))
    cats = list(r)
    
    cat_data = []
    for cat_id, slug in cats:
        prods = c.execute(text(f"SELECT name_de FROM products WHERE category_id={cat_id} LIMIT 5"))
        prod_names = [p[0] for p in prods]
        if prod_names:
            cat_data.append({'id': cat_id, 'products': prod_names})
    
    print(f"Found {len(cat_data)} categories to name.")

    # 2. Ask Gemini to map them
    prompt = """
    You are a grocery categorization expert. I have a list of raw category IDs and sample products in them (in German/Austrian).
    For each, provide:
    1. A beautiful English name (e.g. 'Fresh Produce', 'Dairy & Eggs', 'Bakery', 'Pantry', 'Frozen Foods', 'Beverages', 'Snacks', 'Meat & Seafood', 'Household', 'Personal Care', 'Baby', 'Pets').
    2. A specific Subcategory name in English (e.g. 'Apples', 'Milk', 'Canned Beans').
    3. A specific Subcategory name in German (e.g. 'Äpfel', 'Milch').
    4. A Bootstrap icon class (e.g. 'bi-apple', 'bi-cup-straw', 'bi-egg', 'bi-basket').
    5. A beautiful unsplash image URL representing it (use source.unsplash.com with relevant keywords if possible, or leave blank).
    
    Output strictly valid JSON: a list of objects with keys: id, parent_name_en, subcat_name_en, subcat_name_de, icon, image_url
    
    Data:
    """ + json.dumps(cat_data[:20]) # Test with first 20

    print("Calling Gemini...")
    try:
        response = model.generate_content(prompt)
        text_resp = response.text
        if "```json" in text_resp:
            text_resp = text_resp.split("```json")[1].split("```")[0]
        elif "```" in text_resp:
            text_resp = text_resp.split("```")[1].split("```")[0]
        
        parsed = json.loads(text_resp)
        print("Success for first batch! Got", len(parsed), "results.")
        print(parsed[0])
    except Exception as e:
        print("Error:", e)
        print("Raw response:", response.text if 'response' in locals() else 'No response')
