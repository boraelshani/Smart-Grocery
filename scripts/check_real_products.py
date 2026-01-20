
import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv
import certifi

# Add project root to path
sys.path.append(os.getcwd())

load_dotenv()

def check_products():
    if not os.environ.get('SSL_CERT_FILE'):
        os.environ['SSL_CERT_FILE'] = certifi.where()

    mongo_uri = os.getenv('MONGO_URI')
    client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
    db = client.get_default_database()
    
    products = list(db.products.find().limit(5))
    print(f"Found {len(products)} products in 'products' collection:")
    for p in products:
        print(f"- Name: {p.get('name')}")
        print(f"  Price: {p.get('price')} / {p.get('price_val')}")
        print(f"  Start of Image URL: {str(p.get('image'))[:50]}")
        print(f"  Stores: {p.get('stores')}")
        print("---")

if __name__ == "__main__":
    check_products()
