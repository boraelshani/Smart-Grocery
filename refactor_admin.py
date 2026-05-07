import os, json, requests
from dotenv import load_dotenv

load_dotenv('/Users/drenbuqa/Documents/GitHub/Smart-Grocery/.env')
api_key = os.environ.get('GEMINI_API_KEY')
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={api_key}"

def refactor_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    prompt = f"""
    You are an expert Python Flask & SQLAlchemy developer.
    The following file uses legacy PyMongo `db.collection.find()` syntax. 
    Refactor it to use standard SQLAlchemy ORM syntax. 
    Assume models are imported properly (e.g., `from models.postgres_models import db, Product, Category, Store, Offer, User, PriceHistory, FeaturedDeal, Feedback, CommunityPriceReport`).
    Replace `get_db()` with standard ORM queries.
    Return ONLY the raw refactored Python code without markdown wrapping or explanations.
    
    File content:
    {content}
    """
    
    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    print(f"Refactoring {filepath} via Gemini API...")
    res = requests.post(url, json=data)
    if res.status_code == 200:
        refactored = res.json()['candidates'][0]['content']['parts'][0]['text']
        if refactored.startswith('```python'): refactored = refactored.split('```python')[1]
        if refactored.endswith('```'): refactored = refactored.rsplit('```', 1)[0]
        
        with open(filepath, 'w') as f:
            f.write(refactored.strip() + '\n')
        print(f"Successfully refactored {filepath}")
    else:
        print(f"Error for {filepath}:", res.text)

refactor_file("routes/admin/dashboard.py")
# We will do common.py in chunks or tell it to just refactor the specific lines if it's too big.
